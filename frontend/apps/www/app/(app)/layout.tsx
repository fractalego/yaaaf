import { SiteFooter } from "@/components/site-footer"
import { SiteHeader } from "@/components/site-header"

interface AppLayoutProps {
  children: React.ReactNode
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <div className="overscroll-none ">
      <SiteHeader />
      <main className="flex-1">{children}</main>
    </div>
  )
}
