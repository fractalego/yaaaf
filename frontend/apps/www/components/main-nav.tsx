"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { siteConfig } from "@/config/site"
import { cn } from "@/lib/utils"
import { Icons } from "@/components/icons"

export function MainNav() {
  const pathname = usePathname()

  return (
    <div className="mr-4 hidden md:flex">
      <Link
        href="/"
        className={cn(
          "mr-4 flex items-center space-x-2 transition-colors hover:text-foreground/80 lg:mr-6",
          pathname === "/" ? "text-foreground" : "text-foreground/60"
        )}
        onClick={() => window.location.reload()}
      >
        {/* <Icons.logo className="h-6 w-6" /> */}
        <span className="hidden font-bold lg:inline-block">
          {siteConfig.name}
        </span>
      </Link>
      <nav className="flex items-center gap-4 text-sm lg:gap-6">
        <Link
          href={siteConfig.links.docs}
          target="_blank"
          rel="noopener noreferrer"
          className="text-foreground/60 transition-colors hover:text-foreground/80"
        >
          Docs
        </Link>
      </nav>
    </div>
  )
}
