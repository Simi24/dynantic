# Changelog

## [0.3.1](https://github.com/Simi24/dynantic/compare/dynantic-v0.3.0...dynantic-v0.3.1) (2026-03-27)


### Bug Fixes

* add attestations permission for publishing workflow ([484cec0](https://github.com/Simi24/dynantic/commit/484cec0ec4b576e15008c59fbad4e99747be3a09))

## [0.3.0](https://github.com/Simi24/dynantic/compare/dynantic-v0.2.0...dynantic-v0.3.0) (2026-03-27)


### Features

* add auto-UUID field support with Key(auto=True) and create() method ([d0fce44](https://github.com/Simi24/dynantic/commit/d0fce447b5bec9171e9e4e32c5c7cd69806512b8))
* add batch operations (batch_get, batch_save, batch_delete, batch_writer) ([a80fc8b](https://github.com/Simi24/dynantic/commit/a80fc8beca58f1576cb7edab01f41432f9d96e55)), closes [#5](https://github.com/Simi24/dynantic/issues/5)
* add transaction support (transact_save, transact_write, transact_get) ([34f6a3a](https://github.com/Simi24/dynantic/commit/34f6a3a6bd4887316c8323e4e4f7b367b3e6c2c8)), closes [#6](https://github.com/Simi24/dynantic/issues/6)
* add TTL field support for DynamoDB Time To Live ([50d3216](https://github.com/Simi24/dynantic/commit/50d3216f4e6ef50a63795ca42ac4dbb9fa485586)), closes [#7](https://github.com/Simi24/dynantic/issues/7)
* first commit ([dad9c68](https://github.com/Simi24/dynantic/commit/dad9c6886646dd26ddf6ca6623ae4930d8fb5360))


### Bug Fixes

* address PR review — batch_get retry, BatchWriter exit, TTL dedup ([055d54e](https://github.com/Simi24/dynantic/commit/055d54ee4956a79fd079f26fc5b89802f858a476))


### Code Refactoring

* extract BaseBuilder from Query and Scan builders ([d7e6b36](https://github.com/Simi24/dynantic/commit/d7e6b36836b3b4fd9129f665af7b829b01f856f9)), closes [#4](https://github.com/Simi24/dynantic/issues/4)
* remove redundant scan_page(), update_item(), and DynCondition export ([e021bf8](https://github.com/Simi24/dynantic/commit/e021bf817511d0283d4697a60e7614accdeefcc7))
* split base.py into metaclass, client, and model modules ([6859b07](https://github.com/Simi24/dynantic/commit/6859b074f3f509fae74441ad12ac1ac05aa80e41)), closes [#3](https://github.com/Simi24/dynantic/issues/3)

## [0.2.0](https://github.com/Simi24/dynantic/compare/dynantic-v0.1.0...dynantic-v0.2.0) (2026-02-04)


### Features

* first commit ([385c2d6](https://github.com/Simi24/dynantic/commit/385c2d6348708c300ffd5d47ecbadeb9bc2c2b1b))

## Changelog

All notable changes to this project will be documented in this file.
