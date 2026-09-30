import type { ComponentProps } from 'react';
import { defaultRemarkPlugins } from 'streamdown';
import { Message, MessageContent, MessageResponse } from '@/components/ai-elements/message';
import { Conversation, ConversationContent } from '@/components/ai-elements/conversation';

// Do not pass through URL, node, style or other untrusted attributes.
const components: ComponentProps<typeof MessageResponse>['components'] = {
  strong: ({ children }) => <strong>{children}</strong>,
  em: ({ children }) => <em>{children}</em>,
  a: ({ children }) => <span>{children}</span>,
  img: ({ alt }) => <span>{alt ? `[Imagen omitida: ${alt}]` : '[Imagen omitida]'}</span>,
  pre: ({ children }) => <pre>{children}</pre>,
  code: ({ children }) => <code>{children}</code>,
};
const allowedElements = ['p', 'br', 'strong', 'em', 'del', 'blockquote', 'ul', 'ol', 'li', 'pre', 'code', 'a', 'img', 'h1', 'h2', 'h3', 'h4', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'];
interface MarkdownNode { type: string; children?: MarkdownNode[] }
function literalHtml() {
  return (tree: MarkdownNode) => {
    const visit = (node: MarkdownNode) => {
      if (node.type === 'html') node.type = 'text';
      node.children?.forEach(visit);
    };
    visit(tree);
  };
}
const remarkPlugins = [...Object.values(defaultRemarkPlugins), literalHtml];
export function StaticMarkdown({ text }: { text: string }) {
  return <MessageResponse mode="static" isAnimating={false} animated={false}
    parseIncompleteMarkdown={false} controls={false} plugins={{}}
    remarkPlugins={remarkPlugins} rehypePlugins={[]} skipHtml allowedElements={allowedElements}
    components={components} urlTransform={() => ''} className="static-markdown">
    {text}
  </MessageResponse>;
}
export function DraftMessage({ text }: { text: string }) {
  return <Conversation className="draft-conversation" aria-label="Borrador completo">
    <ConversationContent className="draft-content">
      <Message from="assistant"><MessageContent><StaticMarkdown text={text} /></MessageContent></Message>
    </ConversationContent>
  </Conversation>;
}
