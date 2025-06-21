"use client"

import React from "react"
import { Info } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/registry/default/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/registry/default/ui/dialog"

interface InfoButtonProps {
  title?: string
  message: string
  variant?: "default" | "outline" | "ghost" | "secondary"
  size?: "default" | "sm" | "lg" | "icon"
  className?: string
}

export function InfoButton({
  title = "About",
  message,
  variant = "ghost",
  size = "icon",
  className,
}: InfoButtonProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant={variant}
          size={size}
          className={cn(
            "h-8 w-8 rounded-full transition-colors duration-200 hover:bg-accent hover:text-accent-foreground",
            className
          )}
          aria-label="Show information"
        >
          <Info className="h-4 w-4" />
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Info className="h-5 w-5 text-blue-500" />
            {title}
          </DialogTitle>
        </DialogHeader>

        <div className="mt-4">
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {message}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default InfoButton
