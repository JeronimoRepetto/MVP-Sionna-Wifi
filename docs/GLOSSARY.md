# Glosario

> Vocabulario compartido entre `MVP-Sionna-Wifi` y `wifi-csi-capture`. Si un término
> aparece en un commit, una ficha de trabajo o un nombre de variable, está aquí.

---

## Radio y OFDM

**CSI** · *Channel State Information*
Amplitud y fase de cada subportadora OFDM en la capa física. Es la magnitud central del
proyecto. Cuando una persona se mueve por el campo de RF, su cuerpo (mayormente agua)
refleja y absorbe microondas y altera el patrón multicamino; esa perturbación queda
codificada en la matriz de CSI. De ahí se puede inferir presencia, movimiento y pose, sin
cámaras.

**CIR** · *Channel Impulse Response*
Respuesta del canal en el **dominio del tiempo**: lista de componentes multicamino, cada
una con su amplitud compleja `aᵢ` y su retardo `τᵢ`. Es la salida directa del ray tracing.

**CFR / H(f)** · *Channel Frequency Response*
Respuesta en el **dominio de la frecuencia**. Transformada del CIR:
`H(f) = Σᵢ aᵢ·e^{-j2πf·τᵢ}`. El CSI que reporta el ESP32 es una versión muestreada y
cuantizada de esto.

**OFDM** · *Orthogonal Frequency-Division Multiplexing*
Divide el canal en muchas subportadoras estrechas. Cada una experimenta un desvanecimiento
distinto, y esa diversidad frecuencial es justo lo que aporta información espacial.

**Subportadora** · *subcarrier*
Una de las bandas estrechas de OFDM. En HT40 hay **114** utilizables, con índices
**−57…56** y espaciado de **312,5 kHz**. De ellas, 108 son de datos y el resto pilotos/nulas.

**HT40**
Modo 802.11n con 40 MHz de ancho de banda (dos canales de 20 MHz agregados). Duplica las
subportadoras frente a HT20 y por tanto la resolución. `sig_mode == 1` y `cwb == 1` en la
salida del ESP32.

**Canal 6**
2,437 GHz, frecuencia central. Fijo en todo el proyecto (`WIFI_FREQUENCY`).

**RSSI** · *Received Signal Strength Indicator*
Potencia total recibida en dBm, un solo escalar por frame. Mucho menos informativo que el
CSI, pero útil como referencia y para detectar problemas de AGC.

**Delay spread**
Dispersión temporal de las componentes multicamino, en nanosegundos. Mide cuánto «eco»
tiene la habitación. Métrica de calibración en F4.

**Multicamino** · *multipath*
Las múltiples trayectorias por las que la señal llega del Tx al Rx: directa, reflejada,
refractada, difractada. Su superposición crea el patrón de interferencia que el CSI mide.

**LOS** · *Line of Sight*
Camino directo Tx→Rx, sin rebotes (**cero interacciones**). Normalmente el más fuerte.
⚠️ Hoy el código lo descarta siempre — defecto D-04.

**AGC** · *Automatic Gain Control*
Control automático de ganancia del receptor. Provoca saltos de amplitud no relacionados con
el entorno. El indicador de actividad usa `CV = std/mean`, invariante a escalado lineal,
para compensarlo parcialmente.

**CFO / SFO** · *Carrier / Sampling Frequency Offset*
Desajustes de reloj entre transmisor y receptor. Introducen un offset de fase aleatorio en
cada frame; hay que quitarlo antes de comparar fases (regla N8 del contrato de CSI).

---

## Ray tracing y electromagnetismo

**Sionna RT**
Biblioteca de NVIDIA para trazado de rayos de propagación radio, construida sobre Mitsuba 3.
Es **diferenciable**: permite optimizar propiedades de materiales por descenso de gradiente,
que es la base de F4.
⚠️ La versión instalada es **1.2.2**, cuya API rompe con la 0.x — ver
[`agent/SIONNA_API_CONTRACT.md`](agent/SIONNA_API_CONTRACT.md).

**Mitsuba 3**
Motor de render que Sionna usa como backend geométrico. Aporta el formato de escena XML y
los *variants* de cómputo.

**Variant** (de Mitsuba)
Combinación de backend de cómputo y representación de color, p. ej.
`cuda_ad_mono_polarized` (GPU) o `llvm_ad_mono_polarized` (CPU). **Debe fijarse antes de
importar Sionna** — ver `SIONNA_API_CONTRACT.md §7`.

**OptiX**
API de NVIDIA para trazado de rayos por hardware. Sin ella, Mitsuba cae a CPU. En WSL2
requiere apuntar a `libnvoptix_real.so.1` — ver [`agent/ENVIRONMENT.md §5`](agent/ENVIRONMENT.md).

**SBR** · *Shooting and Bouncing Rays*
Algoritmo de trazado que dispara muchos rayos desde el Tx y sigue sus rebotes. El número de
rayos lo controla `samples_per_src`.

**`max_depth`**
Número máximo de interacciones (rebotes) por camino. Más profundidad = más multicamino y
más coste.

**Difracción** · *diffraction*
Curvatura de la onda en aristas. Permite que la señal llegue a zonas de sombra geométrica.
⚠️ El valor por omisión en Sionna 1.x es `False`, y el código no lo pasa — defecto D-03.

**Refracción** · *refraction*
Transmisión a través de un material. Esencial en este proyecto: los 8 ESP32 están **fuera**
de las paredes, así que la señal debe atravesar hormigón para llegar.

**Reflexión difusa** · *diffuse reflection*
Dispersión en superficies rugosas. En Sionna 1.x el argumento se llama
`diffuse_reflection` (en 0.x era «scattering»).

**ITU-R P.2040**
Recomendación de la UIT con propiedades dieléctricas de materiales de construcción. Sionna
la implementa con identificadores `itu_concrete`, `itu_brick`, `itu_wood`, `itu_metal`,
`itu_wet_ground`.

**`itu_wet_ground`**
Material usado como aproximación del tejido humano: alta permitividad (≈ agua), similar al
comportamiento electromagnético del cuerpo a 2,4 GHz. Valores más precisos (εr 39,2,
σ 1,8 S/m, modelo Cole-Cole) en `wifi-csi-capture/tools/digital_twin_sionna.py`.

**Permitividad relativa** · `εr`
Cuánto polariza un material el campo eléctrico. Junto con la conductividad `σ`, determina
reflexión y absorción. Son los parámetros que F4 optimiza.

**Radio map / mapa de cobertura**
Malla 2D o 3D de potencia recibida. Lo produce `RadioMapSolver`. Aquí se apilan 10
rebanadas de 0,1 a 1,9 m para obtener un volumen.

**Single-Sheet Modeling**
Modelar cada pared como un único plano sin espesor geométrico, dando el grosor real por
propiedad del material. Es lo que Sionna espera.

---

## SMPL y cuerpo humano

**SMPL** · *Skinned Multi-Person Linear model*
Modelo paramétrico de cuerpo humano del Max Planck Institute. Genera una malla de
**6.890 vértices** a partir de parámetros de forma y pose.
⚠️ Los ficheros `.pkl` están bajo [licencia MPI-IS](https://smpl.is.tue.mpg.de/) y **no se
pueden redistribuir** (regla R1 de `AGENTS.md`, defecto D-19).

**SMPL-X**
Extensión de SMPL con manos y cara. La biblioteca `smplx` sirve para ambos; el proyecto usa
`model_type='smpl'`.

**`betas`**
10 parámetros de **forma** corporal (altura, corpulencia…). Variarlos genera sujetos
distintos — clave para la variabilidad del dataset sintético (WP-15).

**`body_pose`**
69 valores = 23 articulaciones × 3 rotaciones en eje-ángulo. Define la **postura**. El mapeo
de índices a articulaciones está en `backend/pose_library.py:39-48`.

**`global_orient`**
3 valores: rotación global del cuerpo (hacia dónde mira).

**`transl`**
Traslación global. ⚠️ En este proyecto siempre `[0,0,0]`: la posición la aplica el frontend
al grupo, no se hornea en los vértices. Ver `agent/CONVENTIONS.md §1`.

**Keyframe de marcha**
Una de las 7 posturas de `WALK_CYCLE_POSES` que definen un ciclo de paso completo. Los
frames intermedios se interpolan linealmente.

---

## Hardware y captura

**ESP32-S3**
Microcontrolador de Espressif con Wi-Fi que expone CSI. El proyecto usa hasta 8 como
receptores.

**ESP-IDF**
Framework de desarrollo de Espressif. Versión 5.5.3.
⚠️ Roto hoy por incompatibilidad de `click` — defecto D-27.

**Modo promiscuo**
Modo del Wi-Fi en el que se reciben todos los frames, no solo los dirigidos al nodo.
Necesario para capturar CSI de forma continua.

**`WIFI_PS_NONE`**
Ahorro de energía desactivado: la radio permanece encendida al 100 %. Imprescindible para
una tasa de CSI estable.

**Ping ICMP como generador de tráfico**
El firmware hace ping al gateway cada 10 ms; cada *Echo Reply* del router provoca una
extracción de CSI. Así se consiguen **100 Hz** sin depender del tráfico ambiental.

**`t0_host_us`**
Epoch Unix en microsegundos en el instante en que el `threading.Barrier` liberó todos los
hilos de captura. Es el ancla que permite una línea de tiempo absoluta común entre nodos:
`t_abs_us = t0_host_us + timestamp_us`. Sin él, los timestamps de distintos nodos no son
comparables.

**Barrier de sincronización**
`threading.Barrier(n)` que retiene cada hilo de captura tras abrir su puerto serie hasta
que todos están listos. Reduce el desfase de arranque entre nodos de ~50-300 ms a ~1-5 ms.

**Filtrado por MAC**
Aceptar solo frames cuyo MAC origen sea el BSSID del router. Sin él, el dataset se contamina
con emisores ajenos.

**`first_word_invalid`**
Flag del driver: si vale 1, los 4 primeros bytes de CSI son basura y se descartan.

**Manifest de sesión**
`session_manifest.json` con escenario, duración, ronda, `t0_host_us`, nodos, puertos,
posiciones y validación de MAC. Da trazabilidad a cada captura.

**Posición / `position_id`**
Ubicación física numerada 1-8 donde se coloca un nodo. 1-4 en el techo, 5-8 en el suelo.
Es la clave de join entre el mundo real y la simulación — ver
[`contracts/SCENE_GEOMETRY.md`](contracts/SCENE_GEOMETRY.md).

**Ronda** · *round*
Grupo de 2 posiciones que se capturan a la vez cuando solo hay 2 nodos disponibles. 4 rondas
cubren las 8 posiciones.

**Filtro de consenso espacial**
`spatial_filter.py`: declara un evento dentro de la zona solo si un número mínimo de enlaces
Tx-Rx se perturban simultáneamente, ponderados por cuánto de su trayecto pasa por la zona.
Distingue actividad interior de movimiento en pasillos adyacentes.

**CV** · *coefficient of variation*
`std(amplitudes) / mean(amplitudes)` sobre las subportadoras de un frame. Indicador de
actividad invariante a escalado, lo que lo hace robusto frente al AGC.

---

## Del proyecto

**Modo mock**
Modo de reserva del backend cuando Sionna no está disponible o la escena no carga. Genera
datos sintéticos con pérdida de espacio libre y desvanecimiento senoidal. Útil para
desarrollar el frontend, **peligroso** si se confunde con datos reales — de ahí el badge
`🟡 Mock Data` en la UI.

**Sim-walk**
Modo en el que, por cada frame de la animación de marcha, se genera la malla SMPL, se
inyecta en la escena de Sionna y se corre la simulación completa. Es lo más costoso que hace
el proyecto y la base de la generación de datasets.

**Gemelo digital** · *digital twin*
Réplica virtual de un entorno físico, calibrada contra mediciones reales para que sus
predicciones sean fiables. Hoy el MVP es una **simulación**; se convierte en gemelo digital
al completar F4.

**Invariante** · `INV-NN`
Propiedad que todo resultado de simulación debe cumplir. Ver
[`agent/PHYSICS_INVARIANTS.md`](agent/PHYSICS_INVARIANTS.md).

**Defecto** · `D-NN`
Entrada del registro [`DEFECTS.md`](DEFECTS.md), con ID estable.

**Paquete de trabajo** · `WP-NN`
Unidad de trabajo ejecutable con criterios de aceptación verificables por comando. Ver
[`work-packages/`](work-packages/).

**Nivel de verificación**
`mock` / `sionna` / `gpu` / `hardware`. Ver
[`agent/VERIFICATION.md`](agent/VERIFICATION.md).

**Sim-to-real**
Entrenar con datos sintéticos y afinar con datos reales. Estrategia de F6 para el modelo de
pose, dado que etiquetar pose real exige captura de movimiento.
