import { ArtefactPage } from "@/registry/custom/artefact-page"
import { get_artefact } from "@/app/artefacts/actions"

// @ts-ignore
export default async function Page({ params }) {
  const parameters = await params
  const aretifact_id = parameters.id
  const artefact = await get_artefact(aretifact_id)

  // @ts-ignore
  return (
    <ArtefactPage
      data={artefact.data}
      code={artefact.code}
      image={artefact.image}
    ></ArtefactPage>
  )
}
