# Componentes de terceros — embedding local

## Runtime

- Hugging Face Transformers.js **3.8.1**, licencia **Apache-2.0**.
- Fuente/versionado: https://github.com/huggingface/transformers.js/tree/3.8.1
- Manifest oficial: https://raw.githubusercontent.com/huggingface/transformers.js/3.8.1/package.json
- Licencia: https://github.com/huggingface/transformers.js/blob/3.8.1/LICENSE
- Instalación local conserva `node_modules/@huggingface/transformers/LICENSE`.

El lock fija las dependencias transitivas, incluyendo `onnxruntime-node` 1.21.0 y
`sharp` 0.34.5 en esta instalación. Sus archivos de licencia se conservan dentro de
`node_modules`. Apache-2.0 de Transformers.js **no cubre automáticamente todas las
transitivas ni los binarios nativos**; consultar sus respectivas licencias antes de
redistribuir. Se instaló con scripts de ciclo de vida deshabilitados.

## Modelo y conversión

- Modelo base: **intfloat/multilingual-e5-small**, licencia declarada **MIT**.
- Autores/procedencia y model card: https://huggingface.co/intfloat/multilingual-e5-small
- Conversión ONNX: https://huggingface.co/Xenova/multilingual-e5-small
- Revisión de conversión fijada: `3acb1fa45c83e69002b1641b37f3cccc132cdd63`.
- Árbol de procedencia: https://huggingface.co/api/models/Xenova/multilingual-e5-small/tree/3acb1fa45c83e69002b1641b37f3cccc132cdd63?recursive=true&expand=false
- Modelo convertido fijado: https://huggingface.co/Xenova/multilingual-e5-small/tree/3acb1fa45c83e69002b1641b37f3cccc132cdd63

`model_manifest.json` conserva los cinco nombres, longitudes e identidades publicadas.
La descarga no incluye el repositorio completo ni una copia adicional de la licencia
del modelo. Este aviso documenta procedencia, no sustituye los términos originales
ni constituye un paquete listo para redistribuir pesos. Conservar la licencia y los
avisos de autoría originales si se prepara tal distribución.

El modelo requiere prefijos ingleses `query: ` y `passage: ` incluso en español,
mean pooling con attention mask y normalización L2. Sus similitudes altas habituales
(aproximadamente 0,7–1,0) no equivalen a calidad, aplicabilidad ni probabilidad de fase.
