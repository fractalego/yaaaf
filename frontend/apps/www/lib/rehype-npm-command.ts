/* eslint-disable turbo/no-undeclared-env-vars */
import { UnistNode, UnistTree } from "types/unist"
import { visit } from "unist-util-visit"

const SITE_URL = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : "https://shadcn-chatbot-kit.vercel.app"

export function rehypeNpmCommand() {
  return (tree: UnistTree) => {
    visit(tree, (node: UnistNode) => {
      if (node.type !== "element" || node?.tagName !== "pre") {
        return
      }

      // npm install.
      if (node.properties?.["__rawString__"]?.startsWith("npm install")) {
        const npmCommand = node.properties?.["__rawString__"]
        node.properties["__npmCommand__"] = npmCommand
        node.properties["__yarnCommand__"] = npmCommand.replace(
          "npm install",
          "yarn add"
        )
        node.properties["__pnpmCommand__"] = npmCommand.replace(
          "npm install",
          "pnpm add"
        )
        node.properties["__bunCommand__"] = npmCommand.replace(
          "npm install",
          "bun add"
        )
      }

      // npx create.
      if (node.properties?.["__rawString__"]?.startsWith("npx create-")) {
        const npmCommand = node.properties?.["__rawString__"]
        node.properties["__npmCommand__"] = npmCommand
        node.properties["__yarnCommand__"] = npmCommand.replace(
          "npx create-",
          "yarn create "
        )
        node.properties["__pnpmCommand__"] = npmCommand.replace(
          "npx create-",
          "pnpm create "
        )
        node.properties["__bunCommand__"] = npmCommand.replace(
          "npx",
          "bunx --bun"
        )
      }

      // npx.
      if (
        node.properties?.["__rawString__"]?.startsWith("npx") &&
        !node.properties?.["__rawString__"]?.startsWith("npx create-")
      ) {
        const npmCommand = node.properties?.["__rawString__"]
        const parts = npmCommand.split(" ")
        const componentName = parts.pop()
        parts.push(`${SITE_URL}/r/${componentName}.json`)
        const modifiedCommand = parts.join(" ")

        node.properties["__npmCommand__"] = modifiedCommand
        node.properties["__yarnCommand__"] = modifiedCommand
        node.properties["__pnpmCommand__"] = modifiedCommand.replace(
          "npx",
          "pnpm dlx"
        )
        node.properties["__bunCommand__"] = modifiedCommand.replace(
          "npx",
          "bunx --bun"
        )
      }
    })
  }
}
