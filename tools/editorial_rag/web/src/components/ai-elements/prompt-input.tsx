// Adapted subset of Vercel AI Elements (Apache-2.0); see THIRD_PARTY_NOTICES.md.
import { cn } from "@/lib/utils";
import type { ComponentProps, HTMLAttributes } from "react";
import { InputGroup, InputGroupAddon, InputGroupTextarea } from "@/components/ui/input-group";
// Local text-only adaptation of upstream form shell: no submit, reset, attachments or provider.
export const PromptInput = ({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("w-full", className)} {...props}><InputGroup className="overflow-hidden">{children}</InputGroup></div>
);
export type PromptInputBodyProps = HTMLAttributes<HTMLDivElement>;

export const PromptInputBody = ({
  className,
  ...props
}: PromptInputBodyProps) => (
  <div className={cn("contents", className)} {...props} />
);

// Preserve upstream InputGroupTextarea composition; native Enter is always a newline.
export const PromptInputTextarea = ({ className, ...props }: ComponentProps<typeof InputGroupTextarea>) => (
  <InputGroupTextarea className={cn("min-h-16", className)} name="message" {...props} />
);
export type PromptInputFooterProps = Omit<
  ComponentProps<typeof InputGroupAddon>,
  "align"
>;

export const PromptInputFooter = ({
  className,
  ...props
}: PromptInputFooterProps) => (
  <InputGroupAddon
    align="block-end"
    className={cn("justify-between gap-1", className)}
    {...props}
  />
);

