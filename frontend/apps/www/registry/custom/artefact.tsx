"use client"
import {createHash} from "crypto"
import * as React from "react"

function Artefact(element: {id: string}) {
  const url: string = "/artefacts/" + element.id
  const colors: Array<string> = [
    "text-red-500",
    "text-yellow-500",
    "text-green-500",
    "text-blue-500",
    "text-purple-500",
    "text-pink-500",
    "text-orange-500",
    "text-teal-500",
    "text-cyan-500",
    "text-emerald-500",
    "text-lime-500",
    "text-rose-500",
    "text-violet-500",
    "text-indigo-500",
    "text-slate-500",
    "text-gray-500",
  ];
  const color_number = createHash("md5").update(url).digest("hex").slice(0, 1).charCodeAt(0) % colors.length;
  return (
    <div className="inline-block">
      <a href={url} target="_blank">
        <div className={color_number[color_number]}>
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
               className="lucide lucide-wrench-icon lucide-wrench">
            <path
              d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
      </a>
    </div>
  )
}

Artefact.displayName = "Artefact";
export {Artefact};
