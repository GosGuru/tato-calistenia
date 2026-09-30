// Manual, allowlisted source installation. Never executes registry commands.
import { mkdir, writeFile, access } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const primitives = ['button', 'input', 'textarea', 'input-group', 'sidebar', 'sheet', 'separator', 'tooltip', 'skeleton', 'use-mobile'];
const urls = new Set([
  ...primitives.map(n => `https://ui.shadcn.com/r/styles/radix-nova/${n}.json`),
  ...['conversation', 'message', 'prompt-input'].map(n => `https://elements.ai-sdk.dev/api/registry/${n}.json`),
  'https://raw.githubusercontent.com/vercel/ai-elements/main/LICENSE',
  'https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md',
]);
const records = [];
async function get(url) {
  if (!urls.has(url)) throw new Error('URL outside allowlist');
  const response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Registry HTTP ${response.status}`);
  const source = await response.text();
  records.push({ url, time: new Date().toISOString(), sha256: createHash('sha256').update(source).digest('hex') });
  return source;
}
async function registry(url) {
  try { return JSON.parse(await get(url)); }
  catch (cause) { throw new Error(`Cannot read official registry: ${url}`, { cause }); }
}
function between(text, first, last) {
  const start = text.indexOf(first), end = text.indexOf(last, start + first.length);
  if (start < 0 || end < 0) throw new Error(`Upstream boundary changed: ${first}`);
  return text.slice(start, end);
}
async function put(path, text) {
  if (!/^(src\/components\/(ui|ai-elements)\/[a-z-]+\.tsx|src\/hooks\/use-mobile\.ts|THIRD_PARTY_NOTICES\.md)$/.test(path)) throw new Error('Invalid output path');
  const target = resolve(root, path);
  if (!target.startsWith(root + '/'.replace('/', process.platform === 'win32' ? '\\' : '/'))) throw new Error('Escaping root');
  // Refuse to overwrite pre-existing local adaptations on reruns.
  try { await access(target); throw new Error(`Already exists: ${path}`); } catch (e) { if (e.code !== 'ENOENT') throw e; }
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, text, { flag: 'wx' });
  console.log(path);
}
for (const name of primitives) {
  const json = await registry(`https://ui.shadcn.com/r/styles/radix-nova/${name}.json`);
  if (json.files.length !== 1) throw new Error('Unexpected registry file count');
  let text = json.files[0].content;
  if (typeof text !== 'string') throw new Error('Missing source');
  text = text.replaceAll('from "cn"', 'from "@/lib/utils"')
    .replaceAll('@/registry/radix-nova/ui/', '@/components/ui/')
    .replaceAll('@/registry/radix-nova/hooks/', '@/hooks/');
  const icons = new Set();
  text = text.replace(/<IconPlaceholder\s+([\s\S]*?)\/>/g, (_, attrs) => {
    const name = attrs.match(/lucide="([^"]+)"/)?.[1];
    if (!name) throw new Error('Unknown icon'); icons.add(name);
    return `<${name} ${attrs.replace(/(?:lucide|tabler|hugeicons|phosphor|remixicon)="[^"]+"\s*/g, '')}/>`;
  });
  text = text.replace('import { IconPlaceholder } from "@/app/(create)/components/icon-placeholder"',
    icons.size ? `import { ${[...icons].join(', ')} } from "lucide-react"` : '');
  if (name === 'sidebar') {
    text = text.replace(/const SIDEBAR_COOKIE_NAME[^\n]*\nconst SIDEBAR_COOKIE_MAX_AGE[^\n]*\n/, '')
      .replace(/\s*\/\/ This sets the cookie[^\n]*\n\s*document.cookie[^\n]*/, '')
      .replace(/const SIDEBAR_WIDTH[^\n]*\n/g, '')
      .replace(/const SIDEBAR_WIDTH_MOBILE[^\n]*\n/g, '')
      .replace(/const SIDEBAR_WIDTH_ICON[^\n]*\n/g, '')
      .replace(/\s*style=\{\s*\{\s*"--sidebar-width": SIDEBAR_WIDTH,[\s\S]*?as React.CSSProperties\s*\}/, '\n            style={style}')
      .replace(/\s*style=\{\s*\{\s*"--sidebar-width": SIDEBAR_WIDTH_MOBILE,[\s\S]*?as React.CSSProperties\s*\}/, '')
      .replaceAll('Toggle Sidebar', 'Alternar navegación')
      .replace('<SheetTitle>Sidebar</SheetTitle>', '<SheetTitle>Navegación</SheetTitle>')
      .replace('Displays the mobile sidebar.', 'Elegí una sección. Cambiar de modo descarta la entrada actual.');
  }
  if (name === 'sheet') {
    // Radix Overlay uses RemoveScroll and injects a style element rejected by CSP.
    // A CSS backdrop retains Content's modal focus trap, hideOthers and dismissal.
    text = text.replace('<SheetPrimitive.Overlay', '<div').replace('React.ComponentProps<typeof SheetPrimitive.Overlay>', 'React.ComponentProps<"div">')
      .replace('data-slot="sheet-overlay"', 'data-slot="sheet-overlay" aria-hidden="true"')
      .replace('>Close<', '>Cerrar navegación<');
  }
  const path = name === 'use-mobile' ? 'src/hooks/use-mobile.ts' : `src/components/ui/${name}.tsx`;
  await put(path, `// Adapted from shadcn/ui radix-nova (MIT); see THIRD_PARTY_NOTICES.md.\n${text}`);
}
for (const name of ['conversation', 'message', 'prompt-input']) {
  const json = await registry(`https://elements.ai-sdk.dev/api/registry/${name}.json`);
  if (json.files.length !== 1 || typeof json.files[0].content !== 'string') throw new Error('Unexpected AI registry');
  const source = json.files[0].content;
  let text;
  if (name === 'conversation') {
    text = 'import { cn } from "@/lib/utils";\nimport type { ComponentProps } from "react";\nimport { StickToBottom } from "use-stick-to-bottom";\n' +
      between(source, 'export type ConversationProps', 'export type ConversationScrollButtonProps');
    text = text.replaceAll('="smooth"', '="instant"');
  } else if (name === 'message') {
    text = 'import { cn } from "@/lib/utils";\nimport { memo } from "react";\nimport type { ComponentProps, HTMLAttributes } from "react";\nimport { Streamdown } from "streamdown";\n' +
      between(source, 'export type MessageProps', 'export type MessageActionsProps') +
      between(source, 'export type MessageResponseProps', 'export type MessageToolbarProps');
    text = text.replace('UIMessage["role"]', '"system" | "user" | "assistant"')
      .replace('const streamdownPlugins = { cjk, code, math, mermaid };', '')
      .replace('      plugins={streamdownPlugins}\n', '');
  } else {
    text = 'import { cn } from "@/lib/utils";\nimport type { ComponentProps, HTMLAttributes } from "react";\nimport { InputGroup, InputGroupAddon, InputGroupTextarea } from "@/components/ui/input-group";\n' +
      '// Local text-only adaptation of upstream form shell: no submit, reset, attachments or provider.\n' +
      'export const PromptInput = ({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) => (\n  <div className={cn("w-full", className)} {...props}><InputGroup className="overflow-hidden">{children}</InputGroup></div>\n);\n' +
      between(source, 'export type PromptInputBodyProps', 'export type PromptInputTextareaProps') +
      '// Preserve upstream InputGroupTextarea composition; native Enter is always a newline.\n' +
      'export const PromptInputTextarea = ({ className, ...props }: ComponentProps<typeof InputGroupTextarea>) => (\n  <InputGroupTextarea className={cn("min-h-16", className)} name="message" {...props} />\n);\n' +
      between(source, 'export type PromptInputFooterProps', 'export type PromptInputToolsProps');
  }
  await put(`src/components/ai-elements/${name}.tsx`, `// Adapted subset of Vercel AI Elements (Apache-2.0); see THIRD_PARTY_NOTICES.md.\n${text}`);
}
const aiLicense = await get('https://raw.githubusercontent.com/vercel/ai-elements/main/LICENSE');
const shadcnLicense = await get('https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md');
const provenance = records.map(r => `- ${r.url}\n  - Consulta UTC: ${r.time}\n  - SHA256: ${r.sha256}`).join('\n');
const copied = primitives.filter(n => n !== 'use-mobile').join(',');
await put('THIRD_PARTY_NOTICES.md', `# Componentes de terceros

Instalación manual desde registros oficiales; sin CLI ni comandos remotos. Los registros no declaran versión semántica: SHA256 del JSON identifica exactamente la fuente consultada. Versiones npm exactas en package.json y resolución en package-lock.json.

## Procedencia

${provenance}

## Archivos y adaptaciones

- shadcn/ui radix-nova → src/components/ui/{${copied}}.tsx y src/hooks/use-mobile.ts. Alias locales, cn local, IconPlaceholder reemplazado por el icono Lucide declarado. Sidebar sin cookie, anchos en CSS local, etiquetas en español. Sheet usa backdrop HTML/CSS en lugar de Radix Overlay/RemoveScroll; Content conserva modalidad, foco, Escape y dismiss externo.
- AI Elements → src/components/ai-elements/{conversation,message,prompt-input}.tsx. Conversation/Content/EmptyState reales sin descarga, scroll instantáneo. Message/Content/Response reales sin ramas, herramientas ni plugins externos. PromptInput conserva composición InputGroup/Body/Footer; shell de texto sin form, provider, reset, adjuntos, captura, blob ni envío con Enter. Es una adaptación explícita, no API upstream completa.
- Streamdown se configura en workspace/DraftMessage.tsx para Markdown estático, sin HTML activo, imágenes, enlaces activos, controles, animación ni plugins. Copiar usa el texto original del controlador.

## Licencia AI Elements

${aiLicense}

## Licencia shadcn/ui

${shadcnLicense}
`);
