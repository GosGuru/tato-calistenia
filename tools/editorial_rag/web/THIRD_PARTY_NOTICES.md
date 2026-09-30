# Componentes de terceros

Instalación manual desde registros oficiales; sin CLI ni comandos remotos. Los registros no declaran versión semántica: SHA256 del JSON identifica exactamente la fuente consultada. Versiones npm exactas en package.json y resolución en package-lock.json.

## Procedencia

- https://ui.shadcn.com/r/styles/radix-nova/button.json
  - Consulta UTC: 2026-09-28T04:05:26.686Z
  - SHA256: c07a8feb7b7ed07ad5279023e45ce23ed7b5b94c7dba3de5c08f30a2aa037de3
- https://ui.shadcn.com/r/styles/radix-nova/input.json
  - Consulta UTC: 2026-09-28T04:05:26.765Z
  - SHA256: 2a94c176dcab621485ad6f902ec9a8b928b1a380a13c196d467ae46923e49044
- https://ui.shadcn.com/r/styles/radix-nova/textarea.json
  - Consulta UTC: 2026-09-28T04:05:26.922Z
  - SHA256: 940fc16b5a019922c5f3ccf64d765776bf96eb735eeb8685df7b8e1c29ab75ad
- https://ui.shadcn.com/r/styles/radix-nova/input-group.json
  - Consulta UTC: 2026-09-28T04:05:26.991Z
  - SHA256: 09df858d8391c409378a88c40a5cf1d3f42ff83bcde8e24c920c37943ce27bda
- https://ui.shadcn.com/r/styles/radix-nova/sidebar.json
  - Consulta UTC: 2026-09-28T04:05:27.085Z
  - SHA256: dfb6a22c81dc4d34b974b368ceb5001c931ac9c077353f2da4ab2ba874e69bf8
- https://ui.shadcn.com/r/styles/radix-nova/sheet.json
  - Consulta UTC: 2026-09-28T04:05:27.173Z
  - SHA256: 2bd0d9a16075ad5d9179b575d71ea1967ba73b1fb39400018b519dd9989607e2
- https://ui.shadcn.com/r/styles/radix-nova/separator.json
  - Consulta UTC: 2026-09-28T04:05:27.316Z
  - SHA256: 1df209eff67aeefa35ff65002ddf9762044a4202ba217b82d447b2f8b8ffd4f2
- https://ui.shadcn.com/r/styles/radix-nova/tooltip.json
  - Consulta UTC: 2026-09-28T04:05:27.384Z
  - SHA256: c639f7ee0511b6d2a1d12e25624952e07209a0d1ddaca47c52bd1e1183efdb89
- https://ui.shadcn.com/r/styles/radix-nova/skeleton.json
  - Consulta UTC: 2026-09-28T04:05:27.491Z
  - SHA256: f956c1b1a8425265e75f6d3439863bd9a515fceb04bbc2da0474d4b80fb23300
- https://ui.shadcn.com/r/styles/radix-nova/use-mobile.json
  - Consulta UTC: 2026-09-28T04:05:27.556Z
  - SHA256: 730abb80c2f6ec4dafd387d757409ad9d8bbfe37c24a3538ad0fabc06e612f1d
- https://elements.ai-sdk.dev/api/registry/conversation.json
  - Consulta UTC: 2026-09-28T04:05:28.014Z
  - SHA256: 7b964b9252cb39218ebbf1e156bcf42be7a049c51e881cf72cc7b7bc2ce31090
- https://elements.ai-sdk.dev/api/registry/message.json
  - Consulta UTC: 2026-09-28T04:05:28.217Z
  - SHA256: c37a2189906cf9e14d95f304d609dc6c0b53e22f78d1d644cddbe1d62284e804
- https://elements.ai-sdk.dev/api/registry/prompt-input.json
  - Consulta UTC: 2026-09-28T04:05:28.511Z
  - SHA256: 660efa7c9a10c204ceeb8d32a320ef430a26776b283a148113a1f672a90af0b8
- https://raw.githubusercontent.com/vercel/ai-elements/main/LICENSE
  - Consulta UTC: 2026-09-28T04:05:28.916Z
  - SHA256: b4f9adb7c568904834d0dd6cc98d16c390d21ca32fc17ae7a267715269bd5529
- https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md
  - Consulta UTC: 2026-09-28T04:05:29.252Z
  - SHA256: 1564074e13439397221ffd522e2e504d56561994a23d371aa5e3ad43e4f5423f

## Archivos y adaptaciones

El rediseño conversacional actual reutiliza estos componentes locales y Lucide ya instalado (ArrowUp).
No se consultaron registros, instalaron paquetes ni modificaron primitives en esta unidad.
Raw compone PromptInput/Textarea/Footer, Button y StaticMarkdown en una columna; no usa EmptyState
para inventar un panel vacío ni un transporte AI SDK. Revisión/comparador conservan sus componentes.
La nueva paleta y geometría viven en CSS local compilado, sin assets remotos ni fuentes externas.

- shadcn/ui radix-nova → src/components/ui/{button,input,textarea,input-group,sidebar,sheet,separator,tooltip,skeleton}.tsx y src/hooks/use-mobile.ts. Alias locales, cn local, IconPlaceholder reemplazado por el icono Lucide declarado. Sidebar sin cookie, anchos en CSS local, etiquetas en español. Sheet usa backdrop HTML/CSS en lugar de Radix Overlay/RemoveScroll; Content conserva modalidad, foco, Escape y dismiss externo.
- AI Elements → src/components/ai-elements/{conversation,message,prompt-input}.tsx. Conversation/Content/EmptyState reales sin descarga, scroll instantáneo. Message/Content/Response reales sin ramas, herramientas ni plugins externos. PromptInput conserva composición InputGroup/Body/Footer; shell de texto sin form, provider, reset, adjuntos, captura, blob ni envío con Enter. Es una adaptación explícita, no API upstream completa.
- Streamdown se configura en workspace/DraftMessage.tsx para Markdown estático, sin HTML activo, imágenes, enlaces activos, controles, animación ni plugins. Copiar usa el texto original del controlador.

## Licencia AI Elements

Copyright 2023 Vercel, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Licencia shadcn/ui

MIT License

Copyright (c) 2023 shadcn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

