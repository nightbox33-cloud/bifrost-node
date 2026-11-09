# Auditoría ofensiva — Bifrost Network (mainnet `thebifrost-mainnet`, chainId 3068)

Fecha: 2026-11-09 · Objetivo: `bifrost-platform/bifrost-node` **v2.2.4 = `7ce8c72c12215831500c343e5e33cf9d6936681a`** (release 2026-11-04)
Rama de trabajo: `arena/3c69a758-bifrost-node` · Artefactos: este directorio (`decode_genesis.py`, `xxh64.py`, `verify_live.py`, `inventory.sh`)

---

## 0. Veredicto

**No hay crítico live demostrable en el código auditado que corre en la mainnet pública.**

Ningún camino permissionless encontrado en el runtime/pallets/precompiles de `thebifrost-mainnet` (v2.2.4) permite sacar más valor del aportado a costa de terceros: todas las transiciones que mueven valor de terceros (BTC del system vault, stake ajeno, tesorería, suministro) exigen una firma de un rol concreto (Authority del socket, Relay Executive, root/Council) **y** una segunda barrera (multisig m-de-n del vault, mayoría de relayers, o `MintableOrigin`).

Los 4 criterios, aplicados al mejor candidato encontrado (§6, gobernanza):

| Criterio | Resultado |
|---|---|
| ¿Bug concreto en código live? | **No**: no hay defecto de implementación; es una *configuración* de gobernanza (parámetros + ejecución Root upstream). |
| ¿Permissionless? | **Sí** para proponer/votar (`Democracy.propose`/`vote` son `EnsureSigned`). |
| ¿Grafo de llamadas y estado reales? | **Sí** (pallet index 51, `Scheduler` real, `RawOrigin::Root` en `bake_referendum`). |
| ¿PnL ≥ 0 tras deshacer? | **Sí, enorme** (Root ⇒ `Sudo.sudo`, `Balances.force_*`). |
| Veredicto bajo tus reglas | **Excluido como crítico**: “rutas privilegiadas (admin/governance/pause/upgrade/sudo/authority)”. Se documenta aparte con números porque es el único camino barato a control total. |

**Salvedad material (no es letra pequeña):** el código de los contratos EVM desplegados (socket, vault, oracle, authority, sistema OmniFi) **no está en ningún repositorio de la org**; sólo hay ABIs y direcciones (`solidity-contract-configs`, último commit 2023-01-04). Esos contratos son los que autorizan (`is_accepted`/`msg_hash`) los pagos del vault, y concentran el TVL. Sin bytecode no se puede afirmar “no hay crítico” en términos absolutos: se afirma sobre lo auditado y se declara el hueco (§8).

---

## 1. REQUISITO PREVIO — estado medido

### 1.1 Enumeración

```
$ gh api "orgs/bifrost-platform/repos?per_page=100" --paginate | jq length
34
$ ... | jq '[.[]|select(.private)]|length'      -> 0
$ ... | jq '[.[]|select(.archived)]|length'     -> 9
$ gh api "orgs/bifrost-platform/repos?type=private&per_page=100" --paginate
[]        (vacío)
```

- **34 repos** en la org (la cifra anterior de “36” venía de una paginación incompleta; con `?per_page=100&--paginate` son 34 y es la que vale). 9 archivados. **0 privados visibles con el token actual.**
- No hay otras orgs/espacios de la fundación con componentes del despliegue: `bifrost-platform` es la única con `bifrost-node`; `Bifrost-network` sólo contiene builds de 2021 (comprobado en la pasada anterior).

### 1.2 Clonado (todas las ramas/tags accesibles: `--depth 1` sobre HEAD, más tags de release leídos por API)

**34/34 repos públicos clonados** + el clon de trabajo + `upstream-bifrost-node` (partial, sin blobs, sólo grafo). HEAD exacto por repo:

| repo | HEAD | uso en esta auditoría |
|---|---|---|
| bifrost-node | `7ce8c72` | fuente de verdad del nodo (v2.2.4) |
| polkadot-sdk | `940ed67` | commit exacto que fija `Cargo.lock` (`branch = bifrost-polkadot-stable2512`) — usado para `pallet_democracy` |
| bifrost-relayer.rs | `03ee6d1` | relayer (PSBT/KMS); sin API HTTP firmante |
| bifrost-frontier | `7b058d3` | EVM/frontier fork |
| bifrost-substrate | `60aa1d7` | substrate fork archivado |
| solidity-contract-configs | `4eccc88` | **ABIs + direcciones** de socket/vault/oracle/authority |
| bifrost-snapshots | `ec5c6e1` | alturas y fechas de snapshot (§2) |
| BifrostHub | `48fce42` | sólo PDFs (sin bytecode) |
| Bifrost-Node-AdminPanel | `790b262` | panel; sin contratos |
| asset-info-v2 / AssetInfo / apps / common / chainlist / gas-price-oracle | `44f6c3b`/`4c2353d`/`9c91135`/`fe0886b`/`8d51171`/`70fb359` | metadatos, frontend, precios; sin componentes desplegados |
| bifrost-relayer.py / -lib / python-lib | `9845064`/`215a951`/`5508785` | archivados 2022 |
| BIFI / BiFi-X / BiFi-staking-protocol / BiFi-Bifrost-Extension-Contract / flashloan-cooking | `ac792dd`/`c323194`/`078c32b`/`2ee02d8`/`6b29224` | dapp lending 2022 y PoCs; no tocan mainnet actual |
| DefiLlama-Adapters / ring-vrf / rust-bitcoincore-rpc / RunnersScenario / ETH_Emulation_Env | `82a78cc`/`0fef826`/`06a6c15`/`6998692`/`aeecbb2` | adaptadores/forks; sin bytecode |
| ethereum / evm / ethers-rs / frontier / substrate / subxt | `755dffa`/`c5c927d`/`51fe937`/`8e354b3`/`120aa3f`/`3866737` | forks upstream |

Submodules: sólo `evm` (`.gitmodules` → `ethereum/tests`), inicializado (`428f218`). **Git LFS: ningún repo lo usa** (`grep -l lfs` sobre `.gitattributes`: 0).

### 1.3 Bloqueos declarados (⇒ cobertura NO completa)

1. **0 repos privados visibles** con el token disponible. Si existen repos privados (infra/despliegue/contratos), quedan fuera. *No se declara cobertura completa.*
2. **El bytecode de los contratos desplegados no está en ningún clon.** `grep -rlis` de las direcciones live sólo devuelve `contractconfig.json` (config) y un JSON del relayer 2022. No hay `.sol` ni artefactos de compilación. El genesis (`genesis.raw.top`, 197 claves) sólo contiene **17 entradas de `EVM.AccountCodes`**, y todas son el stub de 5 bytes `60006000fd` de los **precompile addresses** (0x01–0x09, 0x0100/01/02, 0x0400, 0x0500, 0x0800–03, 0x1000, 0x2000); ninguna es socket/vault/oracle (verificado con `decode_genesis.py`).
3. **RPC público inalcanzable desde el sandbox** (`public-01.mainnet.bifrostnetwork.com` → 000). El estado live se ancla con `specs/bifrost-mainnet.json` (bloque 0) + metadatos de snapshots + el código de v2.2.4. `verify_live.py` deja listo el procedimiento para cerrar esto.

---

## 2. Anclaje del estado live (lo que sí se pudo medir)

| Dato | Valor medido | Fuente |
|---|---|---|
| chain | `thebifrost-mainnet`, `spec_version=2048`, `impl_version=1`, `transaction_version=1` | `runtime/mainnet/src/lib.rs:154-166` |
| chainId EVM | 3068 (testnet 49088) | `runtime/mainnet/src/lib.rs` (EVM `ChainId`) |
| bloque (alto) | 39 544 709 (full, 2026-10-20) · 33 408 325 (archive, 2026-03-20) | `bifrost-snapshots/README.md` + nombres de fichero `...-261020` / `...-260320` |
| **tiempo de bloque real** | **3.013 s** | (39 544 709−33 408 325) bloques / 214 días = 28 675,6 bloques/día ⇒ 86 400/28 675,6. Corrobora el README: “201 600 bloques ≈ 7 días” ⇒ 28 800 bloques/día ⇒ 3,000 s |
| `MILLISECS_PER_BLOCK` en código | 3000 | `runtime/common/constants/src/lib.rs:27` |
| allowance de red | `--rpc-external --rpc-cors all --ethapi debug,trace,txpool`, `--state-pruning archive` | `deploy/mainnet/*.service.example` |

### 2.1 Parámetros del bloque 0 (decodificados con `decode_genesis.py`)

| item | valor |
|---|---|
| `Balances.TotalIssuance` | **853 559 116 BFC** |
| `BfcStaking.Total` | 4 000 000 BFC |
| `BfcStaking.MaxTotalSelected / MaxFullSelected / MaxBasicSelected` | 220 / 20 / 200 |
| comisiones (default/max básico, default/max full) | 10 %/20 %, 30 %/100 % |
| `BfcStaking.InflationConfig` | expect 5 000/10 000/50 000 BFC; **annual 13 %/13 %/13 %**; round 0,0167436 % |
| `RelayManager.Majority` / `InitialMajority` | **1 / 1** |
| `RelayManager.HeartbeatSlashFraction` | 0,2 % |
| `RelayManager.IsHeartbeatOffenceActive` (genesis) | `false` |
| `BfcOffences.IsOffenceActive` / `IsSlashActive` | `true` / `true`; máx. 10 (full) y 5 (basic) ofensas, expiración 4 sesiones |
| `Sudo.Key` | `0xbec4b0d598edce3edc1e2550984a24b7ea069be1` (EOA única) |
| `Council.Members` / `TechnicalCommittee.Members` | **5 / 5** miembros |
| `Democracy.PublicPropCount / ReferendumCount` | 0 / 0 |
| `BtcSocketQueue.*`, `Blaze.*`, `BtcRegistrationPool.*` | **sin estado en genesis** (se configuraron después vía root; el valor actual exige RPC) |

Constantes relevantes del runtime mainnet (v2.2.4, no del genesis):

- `Treasury`: `SpendOrigin = NeverEnsureOrigin` (**no existe la propuesta de gasto on-chain**), `Burn = ()`, `Paymaster = PayFromAccount<Balances, TreasuryAccount>`, `PayoutPeriod = 0`, `RejectOrigin = root | Council>1/2`.
- `BfcUtility.MintableOrigin = Council >1/2` (3 de 5) ⇒ **el Council puede acuñar BFC arbitrariamente** (ruta privilegiada, excluida).
- `Democracy`: `LaunchPeriod 7 d`, `VotingPeriod 7 d`, `VoteLockingPeriod 28 d`, `FastTrack 30 min`, `Enactment 2 d`, **`MinimumDeposit 20 000 BFC`**, `InstantAllowed = true`, `VetoOrigin = 1 miembro del TechCommittee`, `Slash = Treasury`, `Scheduler = Scheduler`.
- `EVM`: `ChainId 3068`, `IdentityAddressMapping` (AccountId de 20 bytes = misma cuenta en EVM y Substrate), `OnChargeTransaction = EVMCurrencyAdapter<Balances, DealWithFees>` (**sólo fee nativo**), `FeeCalculator = FixedGasPrice`, `CallOrigin = EnsureAddressRoot`, `GasLimitPovSizeRatio = 0`, `GasLimitStorageGrowthRatio = 146`.

---

## 3. Inventario de lo auditado (medido)

- **12 pallets del repo** (44 940 líneas Rust) + **13 precompiles** (16 677 líneas) + `runtime/mainnet/src/lib.rs` (1 261 líneas) + `node/mainnet/src/chain_spec.rs` + `deploy/mainnet`.
- **Pallets en mainnet** (26; índice en `construct_runtime`): System 0, Timestamp 2, Aura 3, Session 5, ImOnline 8, Grandpa 9, Balances 10, **RelayManager 20, BfcStaking 21, BfcUtility 22, BfcOffences 23**, Utility 30, Identity 31, SafeMode 32, TxPause 33, **EVM 40, Ethereum 41, BaseFee 42**, Scheduler 50, **Democracy 51**, Council 52, TechCommittee 53, CouncilMembership 54, TechMembership 55, Treasury 56, Preimage 57, **RelayExecutive 58, RelayExecutiveMembership 59, BtcSocketQueue 60, BtcRegistrationPool 61, Blaze 62**, Sudo 99, Migrations 100.
- **No están en mainnet**: `cccp-relay-queue`, `oracle-registry`, `permissioned-authority` (queda storage huérfano en genesis) y **todo `omnifi/*`** (tranche system/investments/tx-registry v1–v3) — sólo en los runtimes *hub*.
- **Runtimes hub**: existen binarios (`node/private-mainnet-hub`, `node/private-testnet-hub`) pero **no hay chain-spec en `specs/`** ni despliegue en `deploy/`: cadenas permissioned, no punto de partida de un atacante permissionless. Aun así se revisó su lógica (§5, filas 11–12).
- **Precompiles mainnet**: 0x01–0x09 (ecrecover, sha256, ripemd, identity, modexp, bn128, blake2, “blake2f”, poseidon), 0x0100 BtcRegistrationPool, 0x0101 BtcSocketQueue, 0x0102 Blaze, 0x0400 BfcStaking, 0x0500 BfcOffences, 0x0800 Governance, 0x0801/02/03 Collective, 0x1000 Balance, 0x2000 RelayManager (vistas). **39 `try_dispatch` y los 39 construyen el origen con `handle.context().caller`**; 0 literales `RawOrigin::Root`/`RawOrigin::Signed` ⇒ un precompile no puede actuar por otra cuenta.

---

## 4. La cadena de custodia, invariante por invariante

El valor de terceros sale de la cadena por cuatro puertas. Ésta es la barrera real de cada una y el fichero:línea que la implementa:

| Puerta | Barrera verificada |
|---|---|
| BTC del **system vault** (PSBT saliente) | `submit_unsigned_psbt` es `ensure_none` pero `validate_unsigned` exige firma del `Authority` sobre `keccak("UnsignedPsbt")‖psbt` y `verify_authority` (`btc-socket-queue/src/pallet/mod.rs:1006-1023`, `impls.rs:117`). Cada salida debe pagar **la dirección de refund registrada** del usuario y el **valor exacto** de la suma de mensajes (`impls.rs:392-455`). La firma final del PSBT la dan los Relay Executives (`submit_signed_psbt`, membresía `RelayExecutiveMembership`) y el vault es un `wsh(sortedmulti(m,n))` con `m = mul_ceil(ratio, n)`, `ratio` por defecto **60 %** (`runtime/mainnet/src/lib.rs:1084`) y `n = Executives::count()` (`impls.rs:322-329`; `set_multi_sig_ratio` es root y exige ≥ 50 %, `mod.rs:784`) ⇒ **hacen falta m claves distintas** (p.ej. n=3 ⇒ 2-de-3; n=5 ⇒ 3-de-5). |
| Mensajes de socket (qué se paga) | `verify_socket_message` (`impls.rs:44-105`): re-encode exacto (`msg.encode() == original`), `keccak(UserRequest(ins_code,params)) == msg_hash` **leído del contrato socket** (`try_get_request`, `impls.rs:631`), `is_accepted()`, `is_bitcoin_outbound`, `token_idx0` clavado por chainId, y dedupe por `sequence`. |
| Stake ajeno / emisión | `bfc-staking` sólo opera con `ensure_signed` = stash o controller **del propio ledger**; `bfc-offences` tiene sus 4 calls en `ensure_root` y sólo se slashea desde `collect_heartbeats` (`relay-manager/impls.rs:158`), no desde una extrinsic permissionless. `mint_native` es `Council>1/2`. |
| Tesorería / suministro | `SpendOrigin = NeverEnsureOrigin` (no hay spend on-chain); `Burn = ()`; `Paymaster` sólo paga fees. `mint` sólo Council>1/2. |

---

## 5. Falsos positivos que se descartaron (y el hecho que los mata)

| # | Hipótesis | Hecho que la mata |
|---|---|---|
| 1 | Fee en ERC20 con `get_bfc_usd_price(max_staleness=0)` ⇒ pagar gas con precio BFC viejo | **Ese pallet no está en mainnet**: `runtime/mainnet/src/lib.rs:1019` usa `pallet_evm::EVMCurrencyAdapter` (sólo nativo). `impl pallet_bifrost_evm_tx_payment::Config` existe **sólo** en `runtime/dev:1186` y `runtime/private-testnet-hub:1131`; el hub mainnet dice explícitamente “Native-token gas only” (`private-mainnet-hub:674`). |
| 2 | Inflación real 6× la nominal (`SECONDS_PER_BLOCK = 3` hardcodeado) | **El bloque es de 3,013 s medidos** (§2). Además `round = 167 436` perbill = (1,13)^(1/730)−1, exactamente 13 % anual con 730 rondas de 14 400 bloques. Sin discrepancia. |
| 3 | El timeline decía “quita Democracy” ⇒ quizá quedó código muerto | **Democracy está vivo**: `#[runtime::pallet_index(51)]` en `runtime/mainnet/src/lib.rs:1218` y `impl pallet_democracy::Config` en `:663`, con `Scheduler` real. No es código muerto; ver §6. |
| 4 | Tesorería drenable por propuesta de gasto | `SpendOrigin = NeverEnsureOrigin` ⇒ `Treasury.spend`/`spend_local` fallan siempre. |
| 5 | Inyectar un outbound falso en `Blaze.outbound_pool` y que el vault pague | `submit_outbound_requests` valida **cada** mensaje con `verify_socket_message` (`blaze/src/pallet/mod.rs:421`) y `validate_unsigned` exige firma de un Relay Executive (`:539`). Blaze además no está activado en genesis (`Blaze.Activation` ausente). |
| 6 | Redirigir un pago BTC a dirección del atacante | La salida debe coincidir con el `refund_address` registrado del usuario y el importe con la suma de los mensajes (`impls.rs:392-455`); `request_set_refund` sólo cambia el tuyo y requiere aprobación de la Authority. |
| 7 | `approve_set_refunds`: la firma **no cubre las direcciones nuevas** (sólo `who`) ⇒ replay con destino cambiado | Mitigado: `ensure!(pending.new == refund_set.1)` (`mod.rs:826`) ata la dirección al valor pendiente en storage, y la entrada se borra al aplicarse ⇒ un replay posterior da `RefundSetDNE`. |
| 8 | `submit_vault_key`: la firma **no cubre `who`** ⇒ rellenar el vault de otro | El mapa de claves está indexado por `authority_id`, la firma se verifica **contra ese mismo `authority_id`** y debe ser miembro de `Executives` (`impls.rs:427`); cada executive sólo puede aportar su propia clave. Griefing como mucho. |
| 9 | `join_candidates(controller, relayer=…)` secuestra un relayer existente | `verify_relayer_existence` rechaza relayer ya unido y controller ya bondeado (`relay-manager/impls.rs:299-313`). |
| 10 | Precompile que despacha por una cuenta arbitraria | 39/39 usan `handle.context().caller`; 0 `RawOrigin` literales. |
| 11 | Doble decremento de `on_flight_cap` en `cccp-relay-queue` | Se suma una vez al aceptar el fast transfer (`mod.rs:528`) y se resta una vez **en la rama que borra** `OnFlightTransfers` (`:711`, `:756`); el poll exige que la entrada exista. Sin doble resta. (Además: hub-only.) |
| 12 | `record_tx`/`record_tx_batch` permissionless en el tx-registry v3 | `T::RecorderOrigin::ensure_origin` (`mod.rs:495`/`538`) y en el hub `RecorderOrigin = EnsureTxRecorder` (`private-mainnet-hub:821`). (Hub-only.) |
| 13 | Slash de stake ajeno por reportar una ofensa | `bfc-offences` no expone ninguna call de reporte: las 4 son `ensure_root`; el slash sólo nace de heartbeats ausentes. |
| 14 | `GasLimitPovSizeRatio = 0` (EVM sin contabilidad de proof-size) | Es bloat/DoS de estado, **no hay transferencia de valor**; `GasLimitStorageGrowthRatio = 146` sigue limitando el crecimiento. No cumple el criterio de robo. |
| 15 | Panics (`refresh_offences` resta sin saturar, `.expect()` en `pay_one_validator_reward`/`refresh_relayer_pool`/`kickout_relayer`, `descriptor.script_code().unwrap()`) | Son **liveness** (parada de bloque/reward), no robo; y las rutas requieren estado que un usuario no provoca (p.ej. `current_session < stored`). Se listan en §7. |
| 16 | `try_psbt_fee_verification` sólo impone **techo** de fee rate (no mínimo) | Sólo lo explota quien ya firma el PSBT (`Authority`), que puede sobrepagar fees a los mineros: pérdida acotada al fee y ruta privilegiada. |

---

## 6. El único camino barato a control total: gobernanza con ejecución Root (NO computa como crítico)

Hecho, no hipótesis: en `polkadot-sdk@940ed67` (`substrate/frame/democracy/src/lib.rs:1609-1616`), un referéndum aprobado se programa con

```rust
T::Scheduler::schedule_named(..., DispatchTime::At(when), None, 63,
    frame_system::RawOrigin::Root.into(), status.proposal)
```

es decir, **la propuesta se ejecuta como Root**. Mainnet tiene ese `Scheduler` configurado (`type Scheduler = Scheduler`, `PalletsOrigin = OriginCaller`) y `Democracy` vivo en el índice 51.

Parámetros desplegados que abaratan el ataque:

- `MinimumDeposit = 20 000 BFC`, **devuelto** en cuanto la propuesta se tabula (`launch_public` hace `unreserve` del depósito) ⇒ el capital sólo está bloqueado ≤ 7 días.
- Umbral de las propuestas públicas = `VoteThreshold::SuperMajorityApprove`, que **no exige quórum de participación**: `nays/√voters < ayes/√electorate` (`vote_threshold.rs:110-111`). Con participación nula, unos pocos BFC en `aye` bastan.
- Plazos: 7 d de votación + 2 d de promulgación; `InstantAllowed = true` (fast-track sólo con 3/5 del TechCommittee).

**PnL**: Root ⇒ `Sudo.sudo(...)` ⇒ `Balances.force_set_balance`/`set_code`/`Council.set_members`/`BfcUtility.mint_native` (vía root que se auto-concede el Council). Coste ≈ 20 000 BFC de capital recuperable + un voto pequeño. Es la definición de “sacar mucho más de lo que pusiste”, pero es **gobernanza**, y tu regla la excluye explícitamente como crítico. Lo que sí es un defecto de *configuración* (no de código) y merece decisión de producto:

1. ¿Tiene que existir `Democracy` en mainnet con `Sudo` vivo y ejecución Root? (La timeline de un commit decía que se quitaba; el código v2.2.4 lo mantiene.)
2. `MinimumDeposit` de 20 000 BFC y **cero quórum** convierten la gobernanza en capturable por un solo titular.
3. La única defensa activa es la cancelación por `root | Council>1/2` o el veto de un miembro del TechCommittee dentro de los 7 días — es decir, **vigilancia humana**, no un invariante.

Mitigación: subir `MinimumDeposit` a un valor comparable al coste de drenar, añadir quórum de participación (`SuperMajorityAgainst` no basta), o retirar `Democracy`/`Sudo` del runtime.

> Nota: esto **no** es “un admin puede hacer rug”. Es “cualquiera sin rol, con 20 000 BFC, puede convertirse en root en ~9 días si el Council/TC no lo cancela”. Aun así, por la regla del encargo, queda fuera de la lista de críticos.

---

## 7. Riesgos menores registrados (ninguno es robo)

| Severidad | Hallazgo | Efecto |
|---|---|---|
| Media (liveness) | `refresh_offences` resta `SessionIndex` sin `saturating_sub`; `.expect()` en `refresh_relayer_pool`/`kickout_relayer`/`pay_one_validator_reward`; `descriptor.script_code().unwrap()` en submits | Un estado inconsistente detiene `on_initialize`/reward. No verificada una ruta permissionless que lo dispare. |
| Media (centralización) | `Majority = 1`, **1 candidato y 1 relayer** en genesis, 1 validador; `submit_executed_request` con `majority()==1`; el vault es m-de-n con `n = Executives::count()` | Un solo operador finaliza requests y produce bloques; y **si `RelayExecutiveMembership` tiene 1 miembro el vault es 1-de-1** (`get_m = mul_ceil(60 %, 1) = 1`). Es configuración operativa, no un bug, pero anula la segunda barrera. Requiere RPC para saber `n` actual. |
| Media (config) | `Sudo` vivo con EOA única `0xbec4b0d598edce3edc1e2550984a24b7ea069be1` | Compromiso de una clave = cadena. Ruta privilegiada (excluida). Valor actual del storage requiere RPC. |
| Baja | `GasLimitPovSizeRatio = 0` | Sin contabilidad de proof-size en EVM ⇒ bloat; `StorageGrowthRatio = 146` acota. |
| Baja | `try_psbt_fee_verification` sin fee mínimo | Sobre-pago de fees por la Authority (pérdida acotada, ruta privilegiada). |
| Baja | `Blaze.submit_outbound_requests` acepta envíos con Blaze desactivado (a propósito) | `OutboundPool` crece sin procesarse; sólo escriben Relay Executives. |
| Informativa | 36 precompiles/“hub” y todo `omnifi/*` no están en mainnet | Ruido de auditoría: no son superficie live. |
| Informativa | RPC expuesto con `--rpc-external --rpc-cors all --ethapi debug,trace,txpool` | `debug_trace*`/`txpool` sobre nodos de operadores: superficie de DoS/abuso, no robo. |

---

## 8. Cobertura NO cubierta (lo que impide el “no crítico” absoluto)

1. **Bytecode de los contratos desplegados** — socket `0xd551F33Ca8eCb0Be83d8799D9C68a368BA36Dd52`, vault `0xD85EB87caB9041ad00764b95796702b1104F42D7`, oracle `0x899aeefda82650EB65FC028a6671ab58Bab76199`, authority `0x…0400`, relayer `0x…2000` (direcciones de `solidity-contract-configs`, config de 2023, **sin verificar on-chain**). El pallet **confía** en `socket.get_request(id).accepted/msg_hash`: si el contrato acepta una petición que no está respaldada por un depósito, el vault paga BTC real. Esa lógica no es auditable desde los clones.
2. **Repos privados** — 0 visibles; no se puede afirmar que no existan.
3. **Estado live** — sin RPC no se verifica: valor actual de `Sudo.Key`, `Blaze.Activation`, `BtcSocketQueue.Authority/Socket`, `BtcRegistrationPool.MultiSigRatio` (m del multisig), tamaño y composición de `RelayExecutiveMembership`, saldo de la tesorería, TVL. Todo lo cuantitativo de este informe es **bloque 0** o código v2.2.4.
4. **Snapshots** (833 GB / 130 GB) no descargados: inviable en el sandbox.

---

## 9. Cómo cerrar el hueco (reproducible)

```bash
# 1. Reproducir el estado del bloque 0 y los parametros que usa el informe
cd audit/2026-11-09 && python3 decode_genesis.py ../../specs/bifrost-mainnet.json

# 2. Reproducir la enumeracion/clonado (idempotente)
ORG=bifrost-platform DEST=$HOME/audit/repos ./inventory.sh

# 3. Contra un nodo (local con snapshot, o RPC con salida a red)
python3 verify_live.py https://<rpc>
#    -> chainId/altura, s/bloque medido, eth_getCode de vault/socket/oracle,
#       y state_getStorage de Sudo.Key, Blaze.Activation, Authority, Socket,
#       MultiSigRatio, Majority, TotalIssuance...

# 4. Bytecode de los contratos (lo que falta para cerrar el §8.1)
cast code 0xd551F33Ca8eCb0Be83d8799D9C68a368BA36Dd52 --rpc-url <rpc> > socket.hex
#    y verificar/descompilar; o pedir a la fundación el repo de contratos.
```

---

## 10. Resumen de una línea

Con el código de v2.2.4 en mano, **el camino permissionless no existe**: cada salida de valor exige firma de rol + segunda barrera (multisig m-de-n, mayoría de relayers o Council>1/2); el único atajo barato a control total es la gobernanza con ejecución Root (`Democracy` + `MinimumDeposit 20 000 BFC`, sin quórum), que tu regla excluye como crítico; y el hueco que impide cerrar el veredicto en términos absolutos es el **bytecode de los contratos EVM desplegados**, que no está en ningún repo de la org.

---

## 11. Segunda pasada (revisión dirigida, 2026-11-09)

Barrido adicional sobre `btc-socket-queue` (`on_initialize` y `composite_psbt`), `blaze` (selección de monedas BNB/Knapsack), `bfc-offences`, `bfc-staking` (cobro de recompensas), `bfc-utility`, `safe-mode`, `im-online` y las 197 claves del genesis. **El veredicto del §10 no cambia**: no apareció ningún camino permissionless de robo. Resultados nuevos:

### 11.1 Hallazgo nuevo (Medio; pérdida del propio usuario, no robo)

Los mensajes de socket con `params.amount <= 546` sats (`DUST_LIMIT`, `primitives/btc-relay/src/lib.rs:36`) **se descartan del PSBT pero siguen sumando al `target`**:

- `pallets/btc-socket-queue/src/pallet/impls.rs:520` filtra `value > 546` **después** de agregar los outputs por `script_pubkey`.
- El `target` del selector se calcula con `outbound_amount_sum` = suma de **todos** los mensajes (`pallet/mod.rs:268` y `:287`) y ese mismo valor se pasa a `composite_psbt` como `target` (`pallet/mod.rs:322`).
- Consecuencia: el importe del mensaje descartado no se paga al usuario, no se devuelve, y se convierte en fee del minero (o se resta del cambio al vault si la estrategia es Knapsack).
- No hay validación de importe mínimo en `verify_socket_message` (`impls.rs:44-97`) ni en la ruta de encolado del pallet.

Ganancia del atacante: **ninguna** (el fee va al minero de Bitcoin, que no elige qué transacción incluye); es pérdida silenciosa de fondos del propio usuario. Para cerrarlo: rechazar o redondear los mensajes ≤ dust antes de encolar, y calcular `target` sobre los outputs efectivos.

### 11.2 Falsos positivos nuevos (descartados, con el hecho que los mata)

| Candidato | Hecho que lo mata |
|---|---|
| El cambio del excedente sólo se crea con `Knapsack`, así que el exceso se pierde como fee | El selector BNB poda `curr_value > target + cost_of_change` (`pallets/blaze/src/pallet/impls.rs:311`) y sólo acepta selecciones con exceso ≤ `cost_of_change = 43·fee_rate` (`btc-socket-queue/src/pallet/mod.rs:308`). Es el comportamiento estándar de Bitcoin Core (evitar el cambio): el exceso no devuelto está acotado por el coste de crear el output de cambio, no es una fuga. |
| `SafeMode` con `EnterDepositAmount = None` ⇒ cualquiera congela la cadena 12 h | Con depósito `None`, `do_enter`/`do_extend` devuelven `NotConfigured` (`substrate/frame/safe-mode/src/lib.rs:476` y `:495`): `enter`/`extend` firmados **no existen** en esta configuración. Safe mode es Root-only (`ForceEnter/Extend/Exit`). |
| `ImOnline.ReportUnresponsiveness = Offences` permite acusar a un validador honesto y hacerle slash | `on_before_session_ending` calcula los offenders por **heartbeats ausentes propios** (`is_online_aux`, `substrate/frame/im-online/src/lib.rs:805-819`); el campo `validators_len` del heartbeat no se usa para acusar a nadie. No hay acusación dirigida por un tercero. |
| `lock_utxos(...).unwrap()` en `on_initialize` ⇒ halt determinista | Sólo falla si un UTXO seleccionado no existe en `Utxos`; y `selected_utxos ⊆ get_utxos()` en la misma llamada (`pallets/blaze/src/pallet/impls.rs:68-80` y `:96-111`). No alcanzable. |
| `.expect("Graceful validator reward payout")` (`pallets/bfc-staking/src/pallet/impls.rs:539/552`) ⇒ halt si el stash está muerto | El único `Err` propagable es `bond_more → reserve(reward)`, y va precedido de `mint_reward(stash)`, que sube el `free` balance exactamente en `reward`. Un candidato vivo tiene el bono reservado (>0), así que su cuenta no puede ser reaped. No alcanzable en operación normal. |
| `refresh_offences` con resta sin `saturating_sub` (`pallets/bfc-offences/src/pallet/impls.rs:78`) ⇒ panic | Sólo desborda si el índice de sesión retrocede (reset/reorg de sesiones), no accionable por un usuario. Sin panic en operación normal. |
| `bfc-utility` mueve Currency | `mint_native` exige `MintableOrigin` (Council > 1/2); `community_proposal`, `add_blocked_account` y `remove_blocked_account` son `ensure_root`. Nada permissionless. |

### 11.3 Genesis: prefijos cerrados

De las 197 claves de `genesis.raw.top`, **todas** las de primer nivel quedan identificadas al añadir los nombres del runtime (`#[frame_support::runtime]`, `runtime/mainnet/src/lib.rs:1148-1256`) y los prefijos bien conocidos (`:code`, `:extrinsic_index`, `:ethereum_schema`, `:grandpa_authorities`). La única que no corresponde a un pallet con estado es `bd2a5293…4e7b9012…`: su segundo half es `twox128(":__STORAGE_VERSION__:")` y vale `0x0000`, es decir, el marcador de versión de storage de un pallet sin más estado en genesis. **0 prefijos sin identificar.**

### 11.4 Lo que sigue faltando

Igual que en §8: bytecode de los contratos EVM (vault/socket/oracle) y estado live por RPC. Sin esos dos, la pérdida de §11.1 no se puede cuantificar (depende de si el contrato acepta solicitudes ≤ 546 sats) y el "no crítico" sigue siendo condicional a la corrección del contrato.
