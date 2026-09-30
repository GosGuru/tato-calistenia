import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StaticMarkdown } from './DraftMessage';

describe('static Markdown boundary', () => {
  it('preserves literal code without double-escaping HTML or ampersands', () => {
    const { container } = render(<StaticMarkdown text={'`<b>literal & value</b>`'} />);
    expect(container.querySelector('code')).toHaveTextContent('<b>literal & value</b>');
    expect(container.querySelector('b')).toBeNull();
  });
  it('keeps plain line breaks and disables all embedded resources', () => {
    const { container } = render(<StaticMarkdown text={'primera\nsegunda\n\n<iframe src="https://example.invalid" />\n\n![ficticia](https://example.invalid/img)'} />);
    expect(screen.getByText(/primera/).textContent).toContain('primera\nsegunda');
    expect(container.querySelector('img, iframe, video, audio, style, script')).toBeNull();
  });
});
