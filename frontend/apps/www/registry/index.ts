import { siteConfig } from "@/config/site"
import { Registry } from "@/registry/schema"

export const registry: Registry = [
  {
    name: "chat",
    type: "registry:ui",
    files: ["ui/chat.tsx"],
    registryDependencies: [
      "button",
      `${siteConfig.url}/r/use-auto-scroll.json`,
      `${siteConfig.url}/r/chat-message.json`,
      `${siteConfig.url}/r/message-input.json`,
      `${siteConfig.url}/r/message-list.json`,
      `${siteConfig.url}/r/prompt-suggestions.json`,
    ],
  },
  {
    name: "use-auto-scroll",
    type: "registry:hook",
    files: ["hooks/use-auto-scroll.ts"],
  },
  {
    name: "chat-message",
    type: "registry:ui",
    files: ["ui/chat-message.tsx"],
    dependencies: ["framer-motion@11"],
    registryDependencies: [
      "button",
      "collapsible",
      `${siteConfig.url}/r/copy-button.json`,
      `${siteConfig.url}/r/markdown-renderer.json`,
    ],
  },
  {
    name: "copy-button",
    type: "registry:ui",
    files: ["ui/copy-button.tsx"],
    registryDependencies: [
      "button",
      `${siteConfig.url}/r/use-copy-to-clipboard.json`,
    ],
  },
  {
    name: "use-copy-to-clipboard",
    type: "registry:hook",
    files: ["hooks/use-copy-to-clipboard.ts"],
    registryDependencies: ["sonner"],
  },
  {
    name: "markdown-renderer",
    type: "registry:ui",
    files: ["ui/markdown-renderer.tsx"],
    dependencies: ["react-markdown@10", "remark-gfm@4", "shiki@1"],
    registryDependencies: [`${siteConfig.url}/r/copy-button.json`],
    tailwind: {
      config: {
        theme: {
          extend: {
            colors: {
              shiki: {
                light: "var(--shiki-light)",
                "light-bg": "var(--shiki-light-bg)",
                dark: "var(--shiki-dark)",
                "dark-bg": "var(--shiki-dark-bg)",
              },
            },
          },
        },
      },
    },
  },
  {
    name: "message-input",
    type: "registry:ui",
    files: ["ui/message-input.tsx"],
    dependencies: ["framer-motion@11", "remeda@2"],
    registryDependencies: [
      "button",
      `${siteConfig.url}/r/use-autosize-textarea.json`,
      `${siteConfig.url}/r/file-preview.json`,
      `${siteConfig.url}/r/audio-visualizer.json`,
      `${siteConfig.url}/r/interrupt-prompt.json`,
      `${siteConfig.url}/r/use-audio-recording.json`,
    ],
  },
  {
    name: "use-autosize-textarea",
    type: "registry:hook",
    files: ["hooks/use-autosize-textarea.ts"],
  },
  {
    name: "message-list",
    type: "registry:ui",
    files: ["ui/message-list.tsx"],
    registryDependencies: [
      `${siteConfig.url}/r/chat-message.json`,
      `${siteConfig.url}/r/typing-indicator.json`,
    ],
  },
  {
    name: "typing-indicator",
    type: "registry:ui",
    files: ["ui/typing-indicator.tsx"],
    tailwind: {
      config: {
        theme: {
          extend: {
            keyframes: {
              "typing-dot-bounce": {
                "0%,40%": { transform: "translateY(0)" },
                "20%": { transform: "translateY(-0.25rem)" },
              },
            },
            animation: {
              "typing-dot-bounce": "typing-dot-bounce 1.25s ease-out infinite",
            },
          },
        },
      },
    },
  },
  {
    name: "prompt-suggestions",
    type: "registry:ui",
    files: ["ui/prompt-suggestions.tsx"],
  },
  {
    name: "file-preview",
    type: "registry:ui",
    files: ["ui/file-preview.tsx"],
    dependencies: ["framer-motion@11"],
  },
  {
    name: "audio-visualizer",
    type: "registry:ui",
    files: ["ui/audio-visualizer.tsx"],
  },
  {
    name: "interrupt-prompt",
    type: "registry:ui",
    files: ["ui/interrupt-prompt.tsx"],
    dependencies: ["framer-motion@11"],
  },
  {
    name: "audio-utils",
    type: "registry:lib",
    files: ["lib/audio-utils.ts"],
  },
  {
    name: "use-audio-recording",
    type: "registry:hook",
    files: ["hooks/use-audio-recording.ts"],
    registryDependencies: [`${siteConfig.url}/r/audio-utils.json`],
  },

  /* ------------------------------------------------------------
   * Demo components
   * ------------------------------------------------------------ */
  {
    name: "chat-demo",
    type: "registry:example",
    description:
      "A chat interface with message bubbles and a form to send new messages",
    files: ["example/chat-demo.tsx"],
  },
  {
    name: "message-input-demo",
    type: "registry:example",
    files: ["example/message-input-demo.tsx"],
  },
  {
    name: "chat-message-demo",
    type: "registry:example",
    files: ["example/chat-message-demo.tsx"],
  },
  {
    name: "message-list-demo",
    type: "registry:example",
    files: ["example/message-list-demo.tsx"],
  },
  {
    name: "typing-indicator-demo",
    type: "registry:example",
    files: ["example/typing-indicator-demo.tsx"],
  },
  {
    name: "markdown-renderer-demo",
    type: "registry:example",
    files: ["example/markdown-renderer-demo.tsx"],
  },
  {
    name: "prompt-suggestions-demo",
    type: "registry:example",
    files: ["example/prompt-suggestions-demo.tsx"],
  },
  {
    name: "copy-button-demo",
    type: "registry:example",
    files: ["example/copy-button-demo.tsx"],
  },
  {
    name: "chat-message-animations-demo",
    type: "registry:example",
    description: "Different animation styles for chat messages",
    files: ["example/chat-message-animations-demo.tsx"],
  },
  {
    name: "chat-message-actions-demo",
    type: "registry:example",
    description: "Chat message with interactive actions",
    files: ["example/chat-message-actions-demo.tsx"],
  },
  {
    name: "chat-message-timestamp-demo",
    type: "registry:example",
    description: "Chat message with timestamp display",
    files: ["example/chat-message-timestamp-demo.tsx"],
  },
  {
    name: "copy-button-custom-message-demo",
    type: "registry:example",
    description: "Copy button with custom success message",
    files: ["example/copy-button-custom-message-demo.tsx"],
  },
  {
    name: "copy-button-code-block-demo",
    type: "registry:example",
    description: "Copy button within a code block",
    files: ["example/copy-button-code-block-demo.tsx"],
  },
  {
    name: "file-preview-demo",
    type: "registry:example",
    description: "A basic file preview implementation",
    files: ["example/file-preview-demo.tsx"],
  },
]
