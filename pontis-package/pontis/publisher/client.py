from pontis.core.base_client import PontisBaseClient
from pontis.core.const import PUBLISHER_REGISTRY_ADDRESS
from pontis.core.entry import serialize_entries, serialize_entry

DEFAULT_N_RETRIES = 3


class PontisPublisherClient(PontisBaseClient):
    def __init__(
        self,
        publisher_private_key,
        publisher_address,
        publisher_registry_address=None,
        network=None,
        oracle_controller_address=None,
        n_retries=None,
    ):
        n_retries = DEFAULT_N_RETRIES if n_retries is None else n_retries
        self.publisher_registry_address = (
            publisher_registry_address
            if publisher_registry_address is not None
            else PUBLISHER_REGISTRY_ADDRESS
        )
        super().__init__(
            publisher_private_key,
            publisher_address,
            network,
            oracle_controller_address,
            n_retries,
        )

    async def _fetch_contracts(self):
        await self._fetch_base_contracts()

    async def update_publisher_address(self, new_address):
        result = await self.send_transaction(
            self.publisher_registry_address,
            "update_publisher_address",
            new_address,
        )
        print(f"Updated publisher address with transaction {result}")

        return result

    async def publish(self, entry):
        result = await self.send_transaction(
            self.oracle_controller_address,
            "submit_entry",
            serialize_entry(entry),
        )
        print(f"Updated entry with transaction {result}")

        return result

    async def publish_many(self, entries):
        if len(entries) == 0:
            print("Skipping publishing as entries array is empty")
            return

        result = await self.send_transaction(
            self.oracle_controller_address,
            "submit_many_entries",
            serialize_entries(entries),
        )

        print(
            f"Successfully sent {len(entries)} updated entries  with transaction {result}"
        )

        return result
