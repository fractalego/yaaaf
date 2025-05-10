import { siteConfig } from "@/config/site"
import { Icons } from "@/components/icons"

export function SiteFooter() {
  return (
    <footer className="py-6 md:px-8 md:py-0">
      <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row">
        <p className="flex items-center text-balance text-center text-sm leading-loose text-muted-foreground md:text-left">
          <span>Built by</span>{" "}
          <Icons.blazity className="mx-1 inline-block h-4 w-4" />
          <span>
            <a
              href={siteConfig.links.twitter}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-blazity underline underline-offset-4"
            >
              Blazity
            </a>
            , based on a project by{" "}
            <a
              href="https://x.com/shadcn"
              target="_blank"
              rel="noreferrer"
              className="font-medium underline underline-offset-4"
            >
              shadcn
            </a>
            . The source code is available on{" "}
            <a
              href={siteConfig.links.github}
              target="_blank"
              rel="noreferrer"
              className="font-medium underline underline-offset-4"
            >
              GitHub
            </a>
            .
          </span>
        </p>
      </div>
    </footer>
  )
}
