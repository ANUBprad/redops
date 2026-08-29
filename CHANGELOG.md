## [0.6.13](https://github.com/ANUBprad/redops/compare/v0.6.12...v0.6.13) (2026-08-29)


### Bug Fixes

* **security:** add org_id to CurrentUser and JWT claims ([01b37a3](https://github.com/ANUBprad/redops/commit/01b37a32d659cb79a71d3c5c61af220e373b3e3e))

## [0.6.12](https://github.com/ANUBprad/redops/compare/v0.6.11...v0.6.12) (2026-08-29)


### Bug Fixes

* **security:** enforce APP_SECRET_KEY in production, auto-generate in dev ([8b10040](https://github.com/ANUBprad/redops/commit/8b1004030d2ba249642e4ed96b54a67d56817553))

## [0.6.11](https://github.com/ANUBprad/redops/compare/v0.6.10...v0.6.11) (2026-08-29)


### Bug Fixes

* **security:** remove anonymous auth bypass in debug mode ([a5957fd](https://github.com/ANUBprad/redops/commit/a5957fdfe042030459a2d82e6b1bada182c7c6cc))

## [0.6.10](https://github.com/ANUBprad/redops/compare/v0.6.9...v0.6.10) (2026-08-29)


### Bug Fixes

* **security:** use config.temporal_task_queue in redteam start_attack_run ([34fd300](https://github.com/ANUBprad/redops/commit/34fd300c2d187170e6f48011d7f736e69bd4c385))

## [0.6.9](https://github.com/ANUBprad/redops/compare/v0.6.8...v0.6.9) (2026-08-29)


### Bug Fixes

* **frontend:** correct 3 API path/method mismatches in api.ts ([b4a06e1](https://github.com/ANUBprad/redops/commit/b4a06e19dd205a0b0c4fe1c1a9c62e469088019e))

## [0.6.8](https://github.com/ANUBprad/redops/compare/v0.6.7...v0.6.8) (2026-08-29)


### Bug Fixes

* **frontend:** align getMetricDistribution to use query params ([f8deaea](https://github.com/ANUBprad/redops/commit/f8deaeaf109d73fa3d248e03b3eec70342a9bd34))

## [0.6.7](https://github.com/ANUBprad/redops/compare/v0.6.6...v0.6.7) (2026-08-29)


### Bug Fixes

* **api:** change profile update from PUT to PATCH ([b4bf972](https://github.com/ANUBprad/redops/commit/b4bf972e7b1026b8b416b34297f08042d4ccc53f))

## [0.6.6](https://github.com/ANUBprad/redops/compare/v0.6.5...v0.6.6) (2026-08-29)


### Bug Fixes

* **api:** change experiment update from PUT to PATCH ([24e95b3](https://github.com/ANUBprad/redops/commit/24e95b396acf366177367e843c7650d799ad5f25))

## [0.6.5](https://github.com/ANUBprad/redops/compare/v0.6.4...v0.6.5) (2026-08-27)


### Bug Fixes

* **frontend:** force dynamic rendering so nonce-based CSP applies in prod ([4666b5d](https://github.com/ANUBprad/redops/commit/4666b5d77592355ef07f2b4181a5b1494aa272f6))
* **frontend:** remove duplicate root page that 500s under dynamic rendering ([29058bc](https://github.com/ANUBprad/redops/commit/29058bcb2c8eb051b733f3acc1ac2717722697b2))

## [0.6.4](https://github.com/ANUBprad/redops/compare/v0.6.3...v0.6.4) (2026-08-27)


### Bug Fixes

* **frontend:** wrap projects/new searchParams in Suspense boundary ([e04ac2b](https://github.com/ANUBprad/redops/commit/e04ac2bec2a98c50d97e07c7e885e15d9f87dc1d))

## [0.6.3](https://github.com/ANUBprad/redops/compare/v0.6.2...v0.6.3) (2026-08-27)


### Bug Fixes

* **frontend:** apply CSP with per-request nonce via middleware ([41c6c7a](https://github.com/ANUBprad/redops/commit/41c6c7ae92844acbbce027eef3dc1e5350b162ec))

## [0.6.2](https://github.com/ANUBprad/redops/compare/v0.6.1...v0.6.2) (2026-08-27)


### Bug Fixes

* **docker:** map frontend dev host port to Next.js container port ([8e5ffc8](https://github.com/ANUBprad/redops/commit/8e5ffc8ffc969a3a4ff76ac4d862f224dce0ec8a))

## [0.6.1](https://github.com/ANUBprad/redops/compare/v0.6.0...v0.6.1) (2026-08-27)


### Bug Fixes

* **docker:** pin Temporal UI to valid tag and fix server healthcheck ([290a9ce](https://github.com/ANUBprad/redops/commit/290a9ced2ad223eb21b47d9746c8601a68e17ce1))

# [0.6.0](https://github.com/ANUBprad/redops/compare/v0.5.0...v0.6.0) (2026-08-27)


### Features

* **providers:** add OpenAI-compatible Groq provider adapter ([6701f40](https://github.com/ANUBprad/redops/commit/6701f40cb35c08d8d5df593f900ca3fbc89d2681))

# [0.5.0](https://github.com/ANUBprad/redops/compare/v0.4.0...v0.5.0) (2026-08-27)


### Features

* **frontend:** add CSP and security headers to Next.js config for XSS hardening ([020e685](https://github.com/ANUBprad/redops/commit/020e685a25415fb016359167a3c977030b40cdc3))

# [0.4.0](https://github.com/ANUBprad/redops/compare/v0.3.0...v0.4.0) (2026-08-27)


### Features

* **security:** add per-route configurable rate limiting with tests ([7cc205a](https://github.com/ANUBprad/redops/commit/7cc205a20db45a0603b82f0bff79d56c74154e6b))

# [0.3.0](https://github.com/ANUBprad/redops/compare/v0.2.1...v0.3.0) (2026-08-27)


### Features

* **evaluation:** add Idempotency-Key support to run creation for safe CI/CD retries ([038eee5](https://github.com/ANUBprad/redops/commit/038eee510bbb81e5a7b8b5e04675d6ee36aba22d))

## [0.2.1](https://github.com/ANUBprad/redops/compare/v0.2.0...v0.2.1) (2026-08-27)


### Bug Fixes

* **backend:** register CORSMiddleware with configured origins ([e1e57c1](https://github.com/ANUBprad/redops/commit/e1e57c1323657a13fe04a59fef36639f1b9420dd))

# [0.2.0](https://github.com/ANUBprad/redops/compare/v0.1.0...v0.2.0) (2026-08-27)


### Bug Fixes

* **agents:** make agent cancellation interrupt execution ([1f06c50](https://github.com/ANUBprad/redops/commit/1f06c50429ba22b0f6417c2876587e0ab9e0fffd))
* **agents:** wire AgentExecutor to use AgentLoop for real execution ([c9b3f05](https://github.com/ANUBprad/redops/commit/c9b3f05e7bdc049a7b58a8833d84dbaad22d6a6a))
* **agents:** wire Temporal workflow to execute AgentLoop via activity ([1d6c5fd](https://github.com/ANUBprad/redops/commit/1d6c5fdf75af8febb80339467139dafd09547f2c))
* **analytics:** fix mypy errors in ExperimentComparisonService ([b0239f4](https://github.com/ANUBprad/redops/commit/b0239f40c64caad9c95ab3551ae95ef2ba44a345))
* **api:** wire replay endpoints to app DI and build explicit response models ([b3404a9](https://github.com/ANUBprad/redops/commit/b3404a999b80f6fcc82985ba13fde6062e38bab3))
* **backend:** add explicit retry policies to Temporal workflow activities ([a66fcf7](https://github.com/ANUBprad/redops/commit/a66fcf7804c2da432b35d7aa40cc6d872a422f61))
* **backend:** configure agent session factory and provider registry for Temporal activities ([27ebb1a](https://github.com/ANUBprad/redops/commit/27ebb1a5bec28596f66f25c699c5a3f6babf75a4))
* **backend:** ensure APP_SECRET_KEY is set in test conftest for CI ([d6dd55e](https://github.com/ANUBprad/redops/commit/d6dd55e95dcbf95d6a981a95bd0a12836b052431))
* **backend:** register missing Temporal activities in DI container ([fb6d4bf](https://github.com/ANUBprad/redops/commit/fb6d4bf70fc6f71bcaef52e896b41e0511052942))
* **backend:** remove stale mypy type: ignore comments ([6c575c4](https://github.com/ANUBprad/redops/commit/6c575c4c14fadf7cb3bd78a6266d82193c3c47b7))
* **backend:** replace non-deterministic datetime.now() with workflow.now() in evaluation workflow ([b1f87e2](https://github.com/ANUBprad/redops/commit/b1f87e2f21a736a78ec52edf49d20962fde070c7))
* **backend:** resolve all mypy strict type errors (28 errors in 6 files) ([7494571](https://github.com/ANUBprad/redops/commit/7494571cf953b0193ced9ea3d1b4bd9d056aaacb))
* **backend:** resolve ruff format and lint errors in test and trajectory files ([b364f30](https://github.com/ANUBprad/redops/commit/b364f309ee1f613c81f6325a82bda968761c8730))
* **ci:** normalize Redis stream typing for strict mypy ([e23e57b](https://github.com/ANUBprad/redops/commit/e23e57be1f514124ef5e0639bd9cf5428538bdc1))
* **ci:** resolve Redis stream typing for strict mypy ([3535d1d](https://github.com/ANUBprad/redops/commit/3535d1d094b105e83600ea51825d93db6bf47d96))
* **config:** remove dangerous secret defaults, fix lifecycle stop ([d80febd](https://github.com/ANUBprad/redops/commit/d80febdf5c7b76aa44ab98289f17013e941cfdd6))
* **db:** add agent trajectory migration ([db635a4](https://github.com/ANUBprad/redops/commit/db635a444bb0b70a372821cbba6d2342c8e80cf7))
* **evaluation:** enforce tuple contracts in replay report value objects ([8c74d4d](https://github.com/ANUBprad/redops/commit/8c74d4d0553ebe7dd2f1c43a857e3a528d723e3b))
* **evaluation:** fix mypy errors and ruff lint issues in workflow and activities ([c9f356d](https://github.com/ANUBprad/redops/commit/c9f356dfa1b3dea164f62629b7b690f4400fbb29))
* **evaluation:** formatting and lint fixes for regression module ([a554137](https://github.com/ANUBprad/redops/commit/a554137dda2084d2bbf6130b913b3c4c4d79cdf0))
* **evaluation:** repair orchestration persistence stage to real repository contract ([5405e76](https://github.com/ANUBprad/redops/commit/5405e760bc120551d5fe2d606948e4617d93774f))
* **evaluation:** type redis trace repository and fix set slicing ([a9f2b76](https://github.com/ANUBprad/redops/commit/a9f2b765b30bc59ceacb1a0aad1887dbd92f9c67))
* **evaluation:** use sa.delete() for mypy-compatible metric cleanup ([6ca5097](https://github.com/ANUBprad/redops/commit/6ca5097a6795f9f2dc410f833ff5d997efcc8b39))
* **evaluation:** wire provider registry and temporal queue ([e464753](https://github.com/ANUBprad/redops/commit/e46475303668602e4e154eed07efed6fe62a90b4))
* **event-bus:** use explicit event types instead of wildcard subscriptions ([a689d2a](https://github.com/ANUBprad/redops/commit/a689d2a7d3fd57f401ed488267c1342a70a79833))
* **event-bus:** use per-event database sessions in audit and notification subscribers ([2255de4](https://github.com/ANUBprad/redops/commit/2255de4bf43c4fe538fae7d35860fea4c92fe00b))
* **frontend:** add .prettierignore to exclude build artifacts from format check ([97cd2b0](https://github.com/ANUBprad/redops/commit/97cd2b05aaf7396b4b1feb663b7e0d6a8ab317b7))
* **frontend:** attach bearer token to API requests and correct SSE paths ([809b063](https://github.com/ANUBprad/redops/commit/809b0637b0318d4cf817b6472b7cac84a713e04e))
* **frontend:** connect dashboard to real analytics data ([1d43f07](https://github.com/ANUBprad/redops/commit/1d43f070877fbd8abcfc79b781184214c03fd27e))
* **frontend:** resolve prettier formatting issues for CI ([96b299d](https://github.com/ANUBprad/redops/commit/96b299d552e32f322c6e948c0a3a0386e52fae18))
* **frontend:** resolve TypeScript errors in run pages ([416b01c](https://github.com/ANUBprad/redops/commit/416b01cd40ea31f494ca3b72dcdf5f158120a182))
* **frontend:** wrap useSearchParams in Suspense boundary for /runs/compare ([c16747f](https://github.com/ANUBprad/redops/commit/c16747f2e582175d8204113708f6982c26736d42))
* **infrastructure:** stabilize application startup and repository tooling ([1caeda7](https://github.com/ANUBprad/redops/commit/1caeda78fe0a64bbaca40417e33d7f2e824310be))
* **metrics:** align embedding metrics with real EmbeddingResponse contract ([e3f4848](https://github.com/ANUBprad/redops/commit/e3f484813b532c5bb439b85dc2f489cb48dcd6de))
* **otel:** fix TracerProvider overwrite bug ([d759a98](https://github.com/ANUBprad/redops/commit/d759a9823e16b774ce6efe4fe1d590190cdb5cf0))
* **prometheus:** add middleware to increment request metrics ([54adaa2](https://github.com/ANUBprad/redops/commit/54adaa24b15cb86ddc5c3cac5b7ad366a3bc1ef3))
* **redteam:** add evaluation_source and document INCONCLUSIVE/SCORE semantics ([355634d](https://github.com/ANUBprad/redops/commit/355634d6e1000fa4d230469279634e10c10c376b))
* **redteam:** formatting and lint fixes for semantic judge ([93e829f](https://github.com/ANUBprad/redops/commit/93e829f761793579e20caea1d0bcf3c1dcdb1d24))
* **redteam:** remove mock data, wire cancel on attack run detail ([e28e9e7](https://github.com/ANUBprad/redops/commit/e28e9e72473ef0c5e2b74d5e71d17243f4eaff02))
* **replay:** clean up imports and formatting for B.9.1.1 ([346fa42](https://github.com/ANUBprad/redops/commit/346fa42e935df1bfd2fecb8f153a07591ac49d4d))
* **replay:** enforce authentication on all trace endpoints ([1cb39ba](https://github.com/ANUBprad/redops/commit/1cb39ba8daa641d97eeaeb8e517a6ea5de94cf7c))
* **replay:** load evaluation traces from persisted database records ([cdcf919](https://github.com/ANUBprad/redops/commit/cdcf91940fa019eecbf81c1a3b888189cef96e89))
* **ruff:** fix import ordering in metric_result.py ([005991a](https://github.com/ANUBprad/redops/commit/005991a123e65702197b8f4ff30a089942c4d6e8))
* **temporal:** add heartbeats to long-running activities ([40b8781](https://github.com/ANUBprad/redops/commit/40b878100ec96aa19d19af52d9585a39b93514d1))
* **temporal:** enforce workflow execution timeouts ([5386a8d](https://github.com/ANUBprad/redops/commit/5386a8d0444264ed088b25c777edb7d096e5a5de))
* **temporal:** make evaluation item execution retry-safe ([e6279da](https://github.com/ANUBprad/redops/commit/e6279daaed9e86d90c99b13bfea5f182673b8f8c))
* **tests:** add prompt_injection and jailbreak to score contract canonical inputs ([74466ad](https://github.com/ANUBprad/redops/commit/74466adb898dabf287a47e5d13368ddeb7dc579e))
* **trajectory:** fix TrajectoryEvaluator conversation_history serialization ([70ec222](https://github.com/ANUBprad/redops/commit/70ec22214df72f33560bb95e446ffdb12a023310))
* **types:** normalize Redis event bus typing ([cc514b5](https://github.com/ANUBprad/redops/commit/cc514b5bfe4eb57723a998c2f47c6aef60783cd0))


### Features

* **agents:** add trajectory persistence layer ([bb130cd](https://github.com/ANUBprad/redops/commit/bb130cdd55e5edb400562c0d064462aadbf10db5))
* **ai:** implement real evaluation pipeline and AI evaluation core ([acda741](https://github.com/ANUBprad/redops/commit/acda7419cf2f635c562414a3585cda95e5e065ae))
* **analytics:** add experiment comparison, metric distribution, pass/fail summary, and p50 latency ([0bb2bf2](https://github.com/ANUBprad/redops/commit/0bb2bf25d596fa3e3dbc113d7f3331e01667d18d))
* **analytics:** add Temporal export workflow and activity for large report exports ([f6195b0](https://github.com/ANUBprad/redops/commit/f6195b0dcea1f6b0351b214aa4b4596987dc28a9))
* **analytics:** implement enterprise analytics and reporting ([ba46170](https://github.com/ANUBprad/redops/commit/ba461704c102f2c5cd89b340d9394791f7e79e32))
* **api:** add experiment and profile REST endpoints ([687330c](https://github.com/ANUBprad/redops/commit/687330cf39212dfe40e64bcc2c71cccfc8e01854))
* **api:** add regression analysis endpoint and replay API methods ([e75d53d](https://github.com/ANUBprad/redops/commit/e75d53d0d7a6b2378985e6f39e18bd975d5760c3))
* **api:** wire start_attack_run endpoint to RedTeamWorkflow via Temporal ([bbe185e](https://github.com/ANUBprad/redops/commit/bbe185e7ec74ca11f9eeb2c460a2c0a2ba794979))
* **attack-runs:** add campaign_results JSON column and persist method ([f2ccca7](https://github.com/ANUBprad/redops/commit/f2ccca764cee37d23182f005655ea3f89a83534f))
* **b6:** agent trajectory evaluation — domain model, tool execution, metrics, evaluator, integration tests ([e4d271d](https://github.com/ANUBprad/redops/commit/e4d271d48f05c1eabd2ab55d145ba3a1ea057b15))
* complete enterprise platform, production readiness, and agent runtime ([83d74cb](https://github.com/ANUBprad/redops/commit/83d74cbb227dbf0407466a8e788dc451cffc0468))
* **composition:** wire export workflow into container, services, and API ([adb577a](https://github.com/ANUBprad/redops/commit/adb577a355e40311c1861fa14424b4eaa560ea45))
* **composition:** wire MetricRegistry into container + startup metric_definitions population ([08467f7](https://github.com/ANUBprad/redops/commit/08467f72aed9a71bd00b94111e96904ed22ad508))
* **composition:** wire RedTeamWorkflow and activity into DI container ([6199131](https://github.com/ANUBprad/redops/commit/61991317e948c2be97313ab349275e3061a2449a))
* **db:** add Alembic migration 018 for experiments and evaluation_profiles tables ([0672b8b](https://github.com/ANUBprad/redops/commit/0672b8b974dd5e2b33f628ee2c3df4995ae18b5c))
* **db:** add metric_definition_id FK to metric_results + migration 020 + fix integrity activity metric versioning ([6c43a23](https://github.com/ANUBprad/redops/commit/6c43a23c2d49a70e5212ba703e38930651e1d776))
* **db:** add metric_definitions table with Alembic migration 019 ([5ef4abe](https://github.com/ANUBprad/redops/commit/5ef4abe0491e93aac4109647c5abe208c53df13d))
* **evaluation:** add regression analysis domain and CLI ([1c812ea](https://github.com/ANUBprad/redops/commit/1c812eab0a4554a6b20b952967437b06f178fe35))
* **evaluation:** add reliability, reproducibility & benchmarking layer (B.4) ([1990bb4](https://github.com/ANUBprad/redops/commit/1990bb41c23527daa6495781be82b204e4c61d09))
* **evaluation:** complete Sprint 1.1 evaluation CRUD ([38f2665](https://github.com/ANUBprad/redops/commit/38f26653172142d1e061892880bf1730b7a774b9))
* **evaluation:** establish explicit metric score contract ([565095a](https://github.com/ANUBprad/redops/commit/565095af5b985c384f6aab17c52779adbeba98d5))
* **evaluation:** execute selected metrics and persist results per item ([b67c87f](https://github.com/ANUBprad/redops/commit/b67c87faaa26115d8e2cb956094c1a233616b291))
* **evaluation:** harden LLM judges against fabricated scores ([7cfade1](https://github.com/ANUBprad/redops/commit/7cfade1f2ef0adc984123d628b1486d82cd1293a))
* **evaluation:** implement end-to-end evaluation pipeline ([d3ebe04](https://github.com/ANUBprad/redops/commit/d3ebe04272d66d15ccd1cd22c315498655ecabbc))
* **evaluation:** record provider provenance in every metric result ([5d4afc8](https://github.com/ANUBprad/redops/commit/5d4afc8ca426e45ca56068c59931ff1327ba58f1))
* **evaluation:** register built-in metrics into production MetricEngine ([1f019c7](https://github.com/ANUBprad/redops/commit/1f019c74846b56992ef4d4463a74459acb591303))
* **evaluation:** wire embedding metrics to real provider boundary ([1c08626](https://github.com/ANUBprad/redops/commit/1c08626c5fc314b937246d75d6812deb872c20b5))
* **evaluation:** wire trace recording, provenance, fingerprint, and threshold verdicts into evaluation workflow ([e589cfb](https://github.com/ANUBprad/redops/commit/e589cfb94745ad4100df4d7d39bd051192a4190b))
* **evaluators:** add evaluator abstraction layer with BaseEvaluatorAdapter, EvaluatorRegistry, and 5 adapter implementations ([64f8a07](https://github.com/ANUBprad/redops/commit/64f8a07b6e1ac827c05103832869f8e244361d1f))
* **event-bus:** implement Phase 5 event subscribers and composition wiring ([85c9dd8](https://github.com/ANUBprad/redops/commit/85c9dd88d285c08a01aa816aeb160f846a9c0809))
* **experiment:** add Experiment domain entity, repository, and service ([4680e36](https://github.com/ANUBprad/redops/commit/4680e361eb60e3534672fb8e8baa7e653bdb238e))
* **frontend:** add delete actions to evaluations and redteam definitions detail pages ([275a2b8](https://github.com/ANUBprad/redops/commit/275a2b889f5d9ba7e5eead0a208d68017665c88e))
* **frontend:** add error boundary component and error.tsx files for main and root layouts ([86b56d3](https://github.com/ANUBprad/redops/commit/86b56d381dd6c596ca75dcd2655baaae0333ab33))
* **frontend:** add experiment management pages (list/create/detail with edit and delete) ([844af57](https://github.com/ANUBprad/redops/commit/844af570686e4cbd279a04ee1265d7d6fc60f8e9))
* **frontend:** add missing API client functions and types for experiments, profiles, datasets, auth refresh, and analytics extras ([9946144](https://github.com/ANUBprad/redops/commit/9946144f99bf3bfaba26706e14c38d769686f5aa))
* **frontend:** add profile management pages (list/create/detail with edit and delete) ([174babf](https://github.com/ANUBprad/redops/commit/174babff56fdafc196f4b464eb1060ba074f6eed))
* **frontend:** add regression analysis component ([d99dbc2](https://github.com/ANUBprad/redops/commit/d99dbc25695dd29959923d40e9d51bfac2a85051))
* **frontend:** add replay viewer component for run details ([e1ccb8c](https://github.com/ANUBprad/redops/commit/e1ccb8ca7ed22e94539ea58940c323d20ab83290))
* **frontend:** add responsive mobile sidebar with hamburger menu ([93c277c](https://github.com/ANUBprad/redops/commit/93c277cd8682de4ee421cc31d244baa5b71d0a59))
* **frontend:** add run comparison page ([b774ef0](https://github.com/ANUBprad/redops/commit/b774ef0802f312812b77195ae127c2e6ebaf0848))
* **frontend:** add settings layout with provider credentials and team management pages ([8639cd8](https://github.com/ANUBprad/redops/commit/8639cd868f80061fbbc0826fe1e0032efdf55cff))
* **frontend:** add skeleton loader components (Skeleton, ListSkeleton, TableSkeleton, CardSkeleton) ([bc04b60](https://github.com/ANUBprad/redops/commit/bc04b60b8efd38b753680f1b542a40bfcd0c0100))
* **frontend:** add sonner toast notification system with Toaster in root layout ([2f4289d](https://github.com/ANUBprad/redops/commit/2f4289d37f7fca08102c6090fe915f514c9133a6))
* **frontend:** complete agent runtime interface and React 19 compatibility ([17439da](https://github.com/ANUBprad/redops/commit/17439da71befde4c687e6da773dceaea8544e4c2))
* **frontend:** complete Phase 5 application foundation ([9727d02](https://github.com/ANUBprad/redops/commit/9727d02e13135df5adabed77bf633d6356d30560))
* **frontend:** enhance run list and details with verdict, cancel, retry ([f3e2f43](https://github.com/ANUBprad/redops/commit/f3e2f43a5e44d58db40bdb8da41e6c12177f0830))
* **frontend:** replace hardcoded projects page with real API integration and add create page ([3144991](https://github.com/ANUBprad/redops/commit/314499116c66c17212b8325c22a01536bfaa157a))
* **frontend:** replace hardcoded reports page with real API integration for dashboard summary, safety trends, and generated reports ([0035afb](https://github.com/ANUBprad/redops/commit/0035afbb5eb5450c4cd0d8fe53dbc331fef6f1ec))
* **frontend:** replace simulated datasets page with functional file parser, preview table, and JSON export ([36417e5](https://github.com/ANUBprad/redops/commit/36417e5f24d347f241355905b1f7527cdf71d7de))
* **metrics:** add CompositeMetric base class with AverageCompositeMetric and WeightedCompositeMetric ([2d30709](https://github.com/ANUBprad/redops/commit/2d30709b2399192b61ef5f7db423621c0c017f55))
* **metrics:** add evaluator_type and required_inputs to all 26 metric implementations ([2610dfc](https://github.com/ANUBprad/redops/commit/2610dfcdbfb1af95190b6fa00867ffc88c328335))
* **metrics:** add EvaluatorType enum and extend MetricDefinition with required_inputs, evaluator_type, plugin_module ([a1df036](https://github.com/ANUBprad/redops/commit/a1df0364333f63d966bb13a88b0807fe8c49465d))
* **metrics:** add MetricRegistry with importlib.metadata entry_points discovery ([0159f6f](https://github.com/ANUBprad/redops/commit/0159f6fffb76367b197d0190a8b174c889fc5266))
* **metrics:** add PromptInjectionMetric and JailbreakMetric ([e048812](https://github.com/ANUBprad/redops/commit/e0488124481c48cf16783a9f8c0d6477f58910c3))
* **observability:** implement Phase 3 live monitoring ([5b78215](https://github.com/ANUBprad/redops/commit/5b7821534f7d82b233a4685f83bcde0d095ad10c))
* **plugins:** add metric plugin template with example CustomAccuracyMetric ([b9770f4](https://github.com/ANUBprad/redops/commit/b9770f46bfabbcc2b6faf6fc880d5937611b82fe))
* **profile:** add EvaluationProfile domain entity, repository, and service ([63eeaa5](https://github.com/ANUBprad/redops/commit/63eeaa5ae781daa629de8fe5c250d3035994a1b6))
* **providers:** implement real EmbeddingProvider boundary on OpenAIProvider ([b1849ce](https://github.com/ANUBprad/redops/commit/b1849ce168784b7252c46ded2e72158504b22589))
* **redteam:** add FindingDetected and CampaignCompleted domain events ([0db2a2b](https://github.com/ANUBprad/redops/commit/0db2a2ba4a96fafd1de3fd8f1a0604e0f4e6173f))
* **redteam:** add semantic effectiveness judge for attack evaluation ([710ec13](https://github.com/ANUBprad/redops/commit/710ec130354a1f71e23eb171a6af6db7d68169a3))
* **redteam:** add Temporal workflow and activity for red team campaigns ([83ae964](https://github.com/ANUBprad/redops/commit/83ae964b4242f8df6b3f2996ed44cb5111122bd0))
* **redteam:** implement B.5 adaptive red team campaign engine ([da768f0](https://github.com/ANUBprad/redops/commit/da768f0a76b90a1b5786373486a487c0fc26e1b1))
* **redteam:** implement Phase 4 safety engine ([b8882dc](https://github.com/ANUBprad/redops/commit/b8882dca9add2e0c3842da56cdb39af12eb0cda3))
* **runtime:** integrate Temporal execution pipeline ([b0916a5](https://github.com/ANUBprad/redops/commit/b0916a514c6e52a2ab2627519e6519f7d1772535))
* **tests:** add tests for MetricRegistry, evaluator adapters, and composite metrics ([8b05396](https://github.com/ANUBprad/redops/commit/8b053963b248a8676f4649f659c1d4d04444be74))


### Performance Improvements

* **evaluation:** reuse embeddings within a single item boundary ([ff9d91c](https://github.com/ANUBprad/redops/commit/ff9d91cc828d2b654576395b11d1e679cadd0673))
