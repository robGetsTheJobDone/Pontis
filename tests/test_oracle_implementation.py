from statistics import median

import pytest
import pytest_asyncio
from pontis.core.entry import construct_entry
from pontis.core.utils import str_to_felt
from starkware.starknet.compiler.compile import compile_starknet_files
from starkware.starknet.testing.starknet import Starknet
from starkware.starkware_utils.error_handling import StarkException
from utils import cached_contract, construct_path

CONTRACT_FILE = construct_path(
    "contracts/oracle_implementation/OracleImplementation.cairo"
)
DEFAULT_DECIMALS = 18
ORACLE_CONTROLLER_ADDRESS = 1771898182094063035988424170791013279488407100660629279080401671638225029234  # random number
AGGREGATION_MODE = 0


@pytest_asyncio.fixture(scope="module")
async def contract_class():
    contract_class = compile_starknet_files(files=[CONTRACT_FILE], debug_info=True)
    return contract_class


@pytest_asyncio.fixture(scope="module")
async def contract_init(contract_class):
    starknet = await Starknet.empty()
    contract = await starknet.deploy(
        contract_class=contract_class, constructor_calldata=[ORACLE_CONTROLLER_ADDRESS]
    )

    return starknet.state, contract


@pytest.fixture
def contract(contract_class, contract_init):
    state, contract = contract_init
    _state = state.copy()
    contract = cached_contract(_state, contract_class, contract)
    return contract


@pytest.mark.asyncio
async def test_deploy(contract):
    return


@pytest.mark.asyncio
async def test_get_decimals(contract):
    result = await contract.get_decimals(str_to_felt("default")).invoke()
    assert result.result.decimals == DEFAULT_DECIMALS

    return


@pytest.mark.asyncio
async def test_update_oracle_controller_address(contract):
    new_oracle_controller_address = ORACLE_CONTROLLER_ADDRESS + 1
    await contract.set_oracle_controller_address(new_oracle_controller_address).invoke(
        caller_address=ORACLE_CONTROLLER_ADDRESS
    )

    try:
        await contract.set_oracle_controller_address(
            new_oracle_controller_address
        ).invoke(caller_address=ORACLE_CONTROLLER_ADDRESS)

        raise Exception(
            "Transaction to update oracle controller address from incorrect address succeeded, but should not have."
        )
    except StarkException:
        pass

    await contract.set_oracle_controller_address(ORACLE_CONTROLLER_ADDRESS).invoke(
        caller_address=new_oracle_controller_address
    )

    return


@pytest.mark.asyncio
async def test_submit_entries(contract, publisher):
    entry = construct_entry(key="eth/usd", value=2, timestamp=1, publisher=publisher)

    await contract.submit_entry(entry).invoke(caller_address=ORACLE_CONTROLLER_ADDRESS)

    result = await contract.get_value([publisher], entry.key, AGGREGATION_MODE).invoke()
    assert result.result.value == entry.value

    second_entry = construct_entry(
        key="btc/usd", value=3, timestamp=2, publisher=publisher
    )

    await contract.submit_entry(second_entry).invoke(
        caller_address=ORACLE_CONTROLLER_ADDRESS
    )

    result = await contract.get_value(
        [publisher], second_entry.key, AGGREGATION_MODE
    ).invoke()
    assert result.result.value == second_entry.value

    # Check that first asset is still stored accurately
    result = await contract.get_value([publisher], entry.key, AGGREGATION_MODE).invoke()
    assert result.result.value == entry.value

    return


@pytest.mark.asyncio
async def test_republish_stale(contract, publisher):
    key = str_to_felt("eth/usd")
    entry = construct_entry(key=key, value=2, timestamp=2, publisher=publisher)

    await contract.submit_entry(entry).invoke(caller_address=ORACLE_CONTROLLER_ADDRESS)

    result = await contract.get_value([publisher], entry.key, AGGREGATION_MODE).invoke()
    assert result.result.value == entry.value

    second_entry = construct_entry(key=key, value=3, timestamp=1, publisher=publisher)

    try:
        await contract.submit_entry(second_entry).invoke(
            caller_address=ORACLE_CONTROLLER_ADDRESS
        )

        raise Exception(
            "Transaction to submit stale price succeeded, but should not have."
        )
    except StarkException:
        pass

    result = await contract.get_value([publisher], key, AGGREGATION_MODE).invoke()
    assert result.result.value == entry.value

    return


@pytest.mark.asyncio
async def test_mean_aggregation(
    contract,
    publisher,
):
    key = str_to_felt("eth/usd")
    entry = construct_entry(key=key, value=3, timestamp=1, publisher=publisher)

    await contract.submit_entry(entry).invoke(caller_address=ORACLE_CONTROLLER_ADDRESS)

    second_publisher = str_to_felt("bar")
    second_entry = construct_entry(
        key=key, value=5, timestamp=1, publisher=second_publisher
    )

    await contract.submit_entry(second_entry).invoke(
        caller_address=ORACLE_CONTROLLER_ADDRESS
    )

    result = await contract.get_value(
        [publisher, second_publisher], key, AGGREGATION_MODE
    ).invoke()
    assert result.result.value == (second_entry.value + entry.value) / 2
    assert result.result.last_updated_timestamp == max(
        second_entry.timestamp, entry.timestamp
    )

    result = await contract.get_entries([publisher, second_publisher], key).invoke()
    assert result.result.entries == [entry, second_entry]

    return


@pytest.mark.asyncio
async def test_median_aggregation(
    contract,
):
    key = str_to_felt("eth/usd")
    prices = [1, 3, 10, 5, 12, 2]
    publishers_str = ["foo", "bar", "baz", "oof", "rab", "zab"]
    publishers = [str_to_felt(p) for p in publishers_str]
    entry = construct_entry(
        key=key, value=prices[0], timestamp=1, publisher=publishers[0]
    )

    await contract.submit_entry(entry).invoke(caller_address=ORACLE_CONTROLLER_ADDRESS)

    entries = [entry]

    for price, additional_publisher in zip(prices[1:], publishers[1:]):
        additional_entry = construct_entry(
            key=key, value=price, timestamp=1, publisher=additional_publisher
        )
        entries.append(additional_entry)

        await contract.submit_entry(additional_entry).invoke(
            caller_address=ORACLE_CONTROLLER_ADDRESS
        )

        result = await contract.get_entries(publishers[: len(entries)], key).invoke()
        assert result.result.entries == entries

        result = await contract.get_value(
            publishers[: len(entries)], key, AGGREGATION_MODE
        ).invoke()
        assert result.result.value == int(median(prices[: len(entries)]))

        print(f"Succeeded for {len(entries)} entries")

    return
