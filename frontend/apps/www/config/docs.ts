import { MainNavItem, SidebarNavItem } from "types/nav"

import { siteConfig } from "@/config/site"

export interface DocsConfig {
  mainNav: MainNavItem[]
  sidebarNav: SidebarNavItem[]
}

export const docsConfig: DocsConfig = {
  mainNav: [
    {
      title: "Docs",
      href: siteConfig.links.docs,
      external: true,
    },
  ],
  sidebarNav: [],
}
