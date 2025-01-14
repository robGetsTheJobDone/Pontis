import json
from abc import ABC, abstractmethod
from os import path

from nile.signer import Signer
from pontis.core.const import NETWORK, ORACLE_CONTROLLER_ADDRESS
from starknet_py.contract import Contract, ContractData, ContractFunction
from starknet_py.net import Client
from starknet_py.net.models import InvokeFunction
from starknet_py.transaction_exceptions import TransactionFailedError
from starkware.crypto.signature.signature import sign
from starkware.starknet.public.abi import get_selector_from_name

MAX_FEE = 0
FEE_SCALING_FACTOR = 1.1  # estimated fee is multiplied by this to set max_fee


class PontisBaseClient(ABC):
    def __init__(
        self,
        account_private_key,
        account_contract_address,
        network=None,
        oracle_controller_address=None,
        n_retries=None,
    ):
        if network is None:
            network = NETWORK
        if oracle_controller_address is None:
            oracle_controller_address = ORACLE_CONTROLLER_ADDRESS

        self.network = network
        self.oracle_controller_address = oracle_controller_address
        self.oracle_controller_contract = None
        self.account_contract_address = account_contract_address
        self.account_contract = None

        assert type(account_private_key) == int, "Account private key must be integer"
        self.account_private_key = account_private_key
        self.signer = Signer(self.account_private_key)

        self.client = Client(self.network, n_retries=n_retries)
        self.latest_nonce = None
        self.next_nonce = None

    @abstractmethod
    async def _fetch_contracts(self):
        pass

    async def wait_for_tx(self, tx_hash, wait_for_accept=False, **kwargs):
        try:
            await self.client.wait_for_tx(tx_hash, wait_for_accept, **kwargs)
        except TransactionFailedError as e:
            # If we errored, might have been due to nonce -> reset nonce optimistically:
            # This is our fallback for cases where a transaction fails unbeknownst to us
            # which would lead to next_nonce > pending_nonce, from which our get_nonce logic
            # has no way to recover (because this case is indistinguishable from the one
            # where next_nonce > pending_nonce because the submitted tx is not yet reflected).
            self.next_nonce = None
            raise e

    async def get_nonce_uncached(self, include_pending=False):
        await self._fetch_contracts()

        block_number = "pending" if include_pending else "latest"

        [nonce] = await self.client.call_contract(
            InvokeFunction(
                contract_address=self.account_contract_address,
                entry_point_selector=get_selector_from_name("get_nonce"),
                calldata=[],
                signature=[],
                max_fee=0,
                version=0,
            ),
            block_number=block_number,
        )
        return nonce

    async def get_nonces(self):
        await self._fetch_contracts()

        self.latest_nonce = await self.get_nonce_uncached()  # use this for estimate_fee
        next_nonce = await self.get_nonce_uncached(include_pending=True)
        # use this for estimating the nonce to use in the tx we send

        # If we have sent a tx recently, use local nonce because network state won't have been updated yet
        if self.next_nonce is not None and self.next_nonce >= next_nonce:
            next_nonce = self.next_nonce + 1
        self.next_nonce = next_nonce

        return next_nonce

    async def _fetch_base_contracts(self):
        if self.oracle_controller_contract is None:
            self.oracle_controller_contract = await Contract.from_address(
                self.oracle_controller_address,
                self.client,
            )

        if self.account_contract is None:
            self.account_contract = await Contract.from_address(
                self.account_contract_address, self.client
            )

    async def get_eth_balance(self):
        if self.network == "testnet":
            eth_address = (
                0x049D36570D4E46F48E99674BD3FCC84644DDD6B96F7C741B1562B82F9E004DC7
            )
        else:
            raise NotImplementedError(
                "PontisBaseClient.get_eth_balance: Unknown network type"
            )

        with open(path.join(path.dirname(__file__), "abi/ERC20.json"), "r") as f:
            erc20_abi = json.load(f)
        contract_data = ContractData.from_abi(eth_address, erc20_abi)
        balance_of_abi = [a for a in erc20_abi if a["name"] == "balanceOf"][0]
        balance_of_function = ContractFunction(
            "balanceOf", balance_of_abi, contract_data, self.client
        )

        result = await balance_of_function.call(self.account_contract_address)

        return result.balance

    async def send_transaction(
        self, to_contract, selector_name, calldata, max_fee=None
    ):
        return await self.send_transactions(
            [(to_contract, selector_name, calldata)], max_fee
        )

    async def send_transactions(self, calls, max_fee=None):
        # Format data for submission
        call_array = []
        offset = 0
        for i in range(len(calls)):
            call_array.append(
                {
                    "to": calls[i][0],
                    "selector": get_selector_from_name(calls[i][1]),
                    "data_offset": offset,
                    "data_len": len(calls[i][2]),
                }
            )
            offset += len(calls[i][2])
        calldata = [x for call in calls for x in call[2]]

        # Estimate fee
        with open(path.join(path.dirname(__file__), "abi/Account.json"), "r") as f:
            account_abi = json.load(f)
        contract_data = ContractData.from_abi(
            self.account_contract_address, account_abi
        )
        execute_abi = [a for a in account_abi if a["name"] == "__execute__"][0]
        execute_function = ContractFunction(
            "__execute__", execute_abi, contract_data, self.client
        )
        await self.get_nonces()  # get nonce as late as possible to decrease the probability of it being stale
        prepared = execute_function.prepare(
            call_array=call_array,
            calldata=calldata,
            nonce=self.latest_nonce,  # have to use latest because we call (not invoke), i.e. run against latest starknet state
        )
        signature = sign(prepared.hash, self.account_private_key)
        # TODO: Change to using AccountClient once estimate_fee is fixed there
        tx = prepared._make_invoke_function(signature=signature)
        estimate = await prepared._client.estimate_fee(tx=tx)

        max_fee_estimate = int(estimate * FEE_SCALING_FACTOR)
        max_fee = (
            max_fee_estimate if max_fee is None else min(max_fee_estimate, max_fee)
        )

        # Submit transaction with fee
        prepared_with_fee = execute_function.prepare(
            call_array=call_array,
            calldata=calldata,
            nonce=self.next_nonce,
            max_fee=max_fee,
        )
        signature = sign(prepared_with_fee.hash, self.account_private_key)
        invocation = await prepared_with_fee.invoke(signature, max_fee=max_fee)

        return invocation
