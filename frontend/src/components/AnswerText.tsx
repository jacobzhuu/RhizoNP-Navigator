import type { ReactNode } from 'react'

const INLINE_MARKDOWN_PATTERN = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let key = 0

  for (const match of text.matchAll(INLINE_MARKDOWN_PATTERN)) {
    const token = match[0]
    const index = match.index ?? 0

    if (index > lastIndex) {
      nodes.push(text.slice(lastIndex, index))
    }

    if (token.startsWith('**')) {
      nodes.push(<strong key={key++}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`')) {
      nodes.push(<code key={key++}>{token.slice(1, -1)}</code>)
    } else {
      nodes.push(<em key={key++}>{token.slice(1, -1)}</em>)
    }

    lastIndex = index + token.length
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }

  return nodes.length > 0 ? nodes : [text]
}

interface AnswerTextProps {
  text: string
  className?: string
}

export function AnswerText({ text, className }: AnswerTextProps) {
  const paragraphs = text.split(/\n+/).filter((paragraph) => paragraph.trim())

  return (
    <div className={className}>
      {paragraphs.map((paragraph, index) => (
        <p key={index}>{renderInlineMarkdown(paragraph)}</p>
      ))}
    </div>
  )
}
