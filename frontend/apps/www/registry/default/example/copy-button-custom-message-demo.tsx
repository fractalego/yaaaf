import { CopyButton } from "@/registry/default/ui/copy-button"

export default function CopyButtonCustomMessageDemo() {
  return (
    <CopyButton
      content="API_KEY_123456"
      copyMessage="API key copied to clipboard!"
    />
  )
}
