"use client"

import * as React from "react"

import { linkifyUrls } from "@/lib/url-utils"

function ArtefactPage(element: { data: string; code: string; image: string }) {
  let data = element.data
  data = data.replaceAll('class="dataframe"', "")
  data = data.replaceAll("text-align: right;", "text-align: left;")
  data = data.replaceAll(
    "<table",
    '<table class="text-left text-sm font-light text-surface dark:text-white"'
  )
  data = data.replaceAll(
    "<tr",
    '<tr class="border-b border-neutral-200 dark:border-white/10"'
  )

  // Process table cell content to make URLs clickable
  data = linkifyUrls(data)
  let html: string = ""
  if (element.image) {
    const image_source = "data:image/png;charset=utf-8;base64," + element.image
    html = `
    <div class="flex">
         <div class="m-5 align-baseline"><img alt="Image" src=${image_source} /></div>
         <div class="m-5 align-baseline"><pre>${element.code}</pre></div>
     </div>
     <div class="columns-[70vw]">
        <div class="m-5 align-baseline">${data}</div>
     </div>
    `
  } else {
    html = `
     <div class="flex">
        <div class="m-5 align-baseline"><pre>${element.code}</pre></div>
     </div>
     <div class="columns-[70vw]">
        <div class="m-5 align-baseline">${data}</div>
     </div>
    `
  }
  return <div dangerouslySetInnerHTML={{ __html: html }}></div>
}

ArtefactPage.displayName = "ArtefactPage"
export { ArtefactPage }
