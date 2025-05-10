import { CopyButton } from "@/registry/default/ui/copy-button"

export default function CopyButtonCodeBlockDemo() {
  return (
    <pre className="relative rounded-lg bg-muted p-4 group/code-block">
      <code className="text-sm">console.log("Hello World")</code>
      <div className="absolute right-2 top-2 opacity-0 group-hover/code-block:opacity-100 transition-opacity">
        <CopyButton content='console.log("Hello World")' />
      </div>
    </pre>
  )
}
