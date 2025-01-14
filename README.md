# Pontis Oracle

This is the repository for the Pontis Oracle on Starknet.

## About

You can read more about the Pontis Oracle [here](https://42labs-xyz.notion.site/Pontis-a0cc65b11f4442e080f5698e2eefe051) and you can see the frontend in action [here](https://pontisoracle.xyz).

### Overview

![Pontis Architecture](/assets/Pontis-Architecture.png)

The Pontis Oracle consists of three smart contracts. The first is the Publisher Registry, which is the most static. This is designed to be updated extremely infrequently because it's state should be permanent (each publisher and their address). The second is the Oracle Controller, which is also designed to be updated only as frequently as absolutely necessary. This is the contract which protocols use, and the one to which publishers publish. In the background, it coordinates the Publisher Registry and the Oracle Implementation(s). The third contract type is Oracle Implementation which contains the logic for storing and aggregating specific key/value data streams. Oracle Implementations can be updated frequently by simply adding them to the Oracle Controller's list of implementation addresses. While there can be many Oracle Implementations to all of which the Oracle Controller write data being published to it, there can be only one primary Oracle Implementation, which is where the Oracle Controller fetches results from when other smart contracts ask it to.

### Deployed Contracts

On testnet, the contracts are deployed at the following addresses:
| Contract | Voyager | Address |
| --- | ----------- | --- |
| PublisherRegistry | [Link](https://goerli.voyager.online/contract/0x07e05e4dea8a62988d9a06ea47bdac34c759a413db5b358e4a3a3d691d9d89e4) | 0x07e05e4dea8a62988d9a06ea47bdac34c759a413db5b358e4a3a3d691d9d89e4 |
| OracleController | [Link](https://goerli.voyager.online/contract/0x013befe6eda920ce4af05a50a67bd808d67eee6ba47bb0892bef2d630eaf1bba) | 0x013befe6eda920ce4af05a50a67bd808d67eee6ba47bb0892bef2d630eaf1bba |
| OracleImplementation (primary) | [Link](https://goerli.voyager.online/contract/0x06302254031a4b67e521c861a433fe7ad2bdd871838ea3a43915cb1d000c5c15) | 0x06302254031a4b67e521c861a433fe7ad2bdd871838ea3a43915cb1d000c5c15 |

## Setup

After you have cloned the repository, run the following commands to set up the repo:
1. `pip install -r requirements.txt`
2. `pip install -r dev-requirements.txt`
3. `pip install -e pontis-package`

# Usage

## Developing Contracts Locally

To ensure your IDE settings and contracts compile correctly, make sure to run any Pontis code after activating your Cairo virtual environment.

Then add this line of code to your shell profile:

```code () { VSCODE_CWD="$PWD" open -n -b "com.microsoft.VSCode" --args $* ;}```

After doing so, open all subsequent windows of the repo from the CLI, using the ```code . ``` command, for correct formatting.

## Pulling Data Locally from Feeds in Deployed Contracts

Make sure you set the following environment variables to be able to interact with the deployed contract:
```
STARKNET_NETWORK=alpha-goerli
```

Then you can use the Starknet CLI to invoke the contract. For instance to get the price of ETH/USD first calculate the key by converting the string to the UTF-8 encoded felt `28556963469423460` (use `str_to_felt("eth/usd")` util in `pontis.core.utils`). Then run the following commands, replacing `<ORACLE_CONTROLLER_ADDRESS>` with the address of the Oracle Controller contract (see above):
```
starknet call --address <ORACLE_CONTROLLER_ADDRESS> --abi contracts/abi/OracleController.json --function get_value --inputs 28556963469423460
```

## Publishing Data to a Feed in a Deployed Contract

The recommended way to publish data is to use the `pontis-publisher` Docker image which has the Pontis SDK baked in, which includes the most up to date contract addresses and the `PontisPublisherClient`. You just need to create a Python script that fetches the data and then publishes it via the `PontisPublisherClient.publish` method. See the setup in `sample-publisher/coinbase` for an example. With the setup there (and an additional file `.secrets.env` with the secret runtime args), we would just have to run:

```
docker build sample-publisher/coinbase/ -t coinbase
docker run --env-file sample-publisher/coinbase/.secrets.env coinbase
```

## Running Tests

To run tests, simply run `pytest .` from the project root.

## Deploying Contracts

To deploy these contracts on Goerli testnet (e.g. to test behavior outside of the production contract), first create a private/public admin key pair for admin actions with both the publisher registry and the Oracle Controller (use `get_random_private_key` and `private_to_stark_key` in `starkware.crypto.signature.signature`).

Then run the following commands, replacing `<ADMIN_PUBLIC_KEY>` with the public key you generated in the previous step. Replace `<ADMIN_ADDRESS>`, `<PUBLISHER_REGISTRY_ADDRESS>` and `<ORACLE_CONTROLLER_ADDRESS>` with the addresses of the first, second and third contract deployed in the steps below, respectively.

```
export STARKNET_NETWORK=alpha-goerli
starknet-compile contracts/erc20/ERC20.cairo --abi contracts/abi/ERC20.json --output erc20_compiled.json && cp contracts/abi/ERC20.json pontis-package/pontis/core/abi/ERC20.json
starknet-compile --account_contract contracts/account/Account.cairo --abi contracts/abi/Account.json --output account_compiled.json && cp contracts/abi/Account.json pontis-package/pontis/core/abi/Account.json
starknet deploy --contract account_compiled.json --inputs <ADMIN_PUBLIC_KEY>
starknet deploy --contract account_compiled.json --inputs <PUBLISHER_PUBLIC_KEY>
starknet-compile contracts/publisher_registry/PublisherRegistry.cairo --abi contracts/abi/PublisherRegistry.json --output publisher_registry_compiled.json
starknet deploy --contract publisher_registry_compiled.json --inputs <ADMIN_ADDRESS>
starknet-compile contracts/oracle_controller/OracleController.cairo --abi contracts/abi/OracleController.json --output oracle_controller_compiled.json && cp contracts/abi/OracleController.json pontis-ui/src/abi/OracleController.json
starknet deploy --contract oracle_controller_compiled.json --inputs <ADMIN_ADDRESS> <PUBLISHER_REGISTRY_ADDRESS>
starknet-compile contracts/oracle_implementation/OracleImplementation.cairo --abi contracts/abi/OracleImplementation.json --output oracle_implementation_compiled.json
starknet deploy --contract oracle_implementation_compiled.json --inputs <ORACLE_CONTROLLER_ADDRESS>
```

Finally, you must add the Oracle Implementation to the Controller. You can use the `add_oracle_implementation` method of the `PontisAdminClient` class in `pontis.admin.client`. For instance, after replacing `<ORACLE_IMPLEMENTATION_ADDRESS>` with the actual address you would run the `add_oracle_implementation.py` script in sample-publisher/utils. After replacing the Publisher Registry, run the `register_all_publishers.py` in the same location.

# Release Flow

The release flow depends on which parts of the code base changed. Below is a mapping from which parts of the code base changed to how to release the updates.

## Contracts

First, compile and then redeploy the contract(s) that have changed. See the section above "Deploying Contracts" for details.

Then, depending on which contracts were redeployed, you have to take further steps:
- If it was merely the oracle implementation contract that was updated, add it to the Oracle Controller's oracle implementations so that it can run in shadow mode. Finally, you need to set that oracle implementation as the primary one by using the `set_primary_oracle` method of the `PontisAdminClient` class in `pontis.admin.client`.
- If oracle registry is updated, you will first have to pull existing publishers and keys and write them to the new publisher registry. It is probably easiest to do this off-chain, by using the getter functions on the old publisher registry and then using the admin key to effectively re-register all the publishers in the new register. You must also update the `PUBLISHER_REGISTRY_ADDRESS` variable in `pontis.core.const` and then follow the steps to release a new version of the pontis package. Finally, you'll have to update the Oracle Controller's Publisher Registry address which you can do using the `update_publisher_registry_address` method of the `PontisAdminClient` class in `pontis.admin.client`.
- Finally, if the Oracle Controller is updated, you'll have to update the address in pontis-package (`pontis.core.const`), in this README (above), in the sample consumer (`contracts/sample_consumer/SampleConsumer.cairo`) and in pontis-ui (`src/services/address.service.ts`). Then you'll have to follow the release processes for those components. Finally, make sure to coordinate with protocols to update their references.

## Pontis Package
First, make sure to set the environmental variable `PYPI_API_TOKEN`.

To create a new version, just navigate into `pontis-package` and run `bumpversion <part>` (where `<part>` is major, minor or patch). Then run `python3 -m build` to generate the distribution archives. Finally upload the new distribution with `twine upload dist/* -u __token__ -p $PYPI_API_TOKEN`. Make sure to run `git push --tags` once you've done that.

When you merge to master, the Pontis Publisher GHA will automatically release a new Docker base image with the appropriate tag (the new version of the `pontis` package). See the "Pontis Publisher Docker Base Image" section for more details.

## Pontis UI
Netlify will automatically deploy previews on push if a pull request is open and will redeploy the main website on merge to master.

## Pontis Publisher Docker Base Image
Run the following commands to build a new base image for pontis-publisher locally. Use the `latest` tag for testing:
```
docker build . -t 42labs/pontis-publisher
docker push 42labs/pontis-publisher:latest
```

pontis-publisher base images are versioned together with the pontis Python package because when the pontis package is updated, a new Docker image should always be released. If the Docker image needs to be updated for a reason other than a new pontis package release, the release flow will overwrite the pontis package. A new Docker image is automatically tagged with the appropriate version and pushed to Dockerhub by the GHA release flow, so no need to do this locally.

## Sample Publisher
If your changes involve changes to the fetching and publishing code, navigate to `publisher/manage-deployment` and run `scp -i LightsailDefaultKey-us-east-2.pem -r ../sample-publisher/all ubuntu@<IP_ADDRESS>:` to copy over the code again, where `IP_ADDRESS` is the IP address of the Lightsail instance. The existing instance will automatically rebuild the docker image using that new code.

If your changes are to the cron command, it is easiest to ssh into the instance and edit the cron command there directtly using `crontab -e`.

# Staging Environment

## Separate Environment
We have a staging environment set up in order to be able to test our code without affecting the production environment.

On testnet, the staging contracts are deployed at the following addresses:
| Contract | Voyager | Address |
| --- | ----------- | --- |
| PublisherRegistry | [Link](https://goerli.voyager.online/contract/0x07cc3a9a4d1fe77b022e6e35007f0e1d8fdf8b87a8bdbcb2609c5d4e83817797) | 0x07cc3a9a4d1fe77b022e6e35007f0e1d8fdf8b87a8bdbcb2609c5d4e83817797 |
| OracleController | [Link](https://goerli.voyager.online/contract/0x02f2a6fefb5474490cf737da1d1603f5914e525d3e4abd8d87a8e139a864baff) | 0x02f2a6fefb5474490cf737da1d1603f5914e525d3e4abd8d87a8e139a864baff |
| OracleImplementation (primary) | [Link](https://goerli.voyager.online/contract/0x00dfcf1028eaad141e4f135019847aa3684918d639e8bccf74c9e57851ec0c7d) | 0x00dfcf1028eaad141e4f135019847aa3684918d639e8bccf74c9e57851ec0c7d |

The admin contract is identical to the one used in production. Staging has a separate Publisher Registry, so accounts registered in production will not be registered there. The Pontis publisher account that is registered is located at 3251373723367219268498787183941698604007480963314075130334762142902855469511.

The main part of our CI setup that uses the staging environment is the update prices GHA.

## Staging in Shadow Mode
Sometimes it is important to test how contracts function in the real world. We can do that for Oracle Implementations, by running them in shadow mode.

In order to run an Oracle Implementation in shadow mode, first deploy the Oracle Implementation contract. Then, run the `add_oracle_implementation.py` script in `publisher/utils` with the address from the new Oracle Implementation. The new contract is now in shadow mode, i.e. it receives updates (writes) from the Oracle Controller, but is not used to answer queries (reads). You can read from the new Oracle Implementation contract directly in order to test the new logic.

If the new Oracle Implementation has passed testing and is ready to be promoted to the primary Oracle Implementation (the one used for answering queries), run the `set_primary_oracle_implementation.py` script in `publisher/utils` with the address from the new Oracle Implementation. Once that is complete and the new system is up and running, you can retire the old Oracle Implementation using the `deactivate_oracle_implementation.py` script located in the same directory.