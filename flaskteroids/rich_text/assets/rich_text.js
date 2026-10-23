// Flaskteroids currently supports text-only rich text.
document.addEventListener("trix-file-accept", (event) => {
  if (event.target.hasAttribute("data-flaskteroids-rich-text")) event.preventDefault()
})

document.addEventListener("trix-attachment-add", (event) => {
  if (event.target.hasAttribute("data-flaskteroids-rich-text")) event.attachment.remove()
})

document.addEventListener("trix-initialize", (event) => {
  if (!event.target.hasAttribute("data-flaskteroids-rich-text")) return
  const editor = event.target
  editor.toolbarElement.querySelector('[data-trix-button-group="file-tools"]')?.remove()

  if (!editor.hasAttribute("aria-label") && !editor.hasAttribute("aria-labelledby")) {
    const labels = Array.from(document.querySelectorAll("label")).filter(label => label.htmlFor === editor.id)
    labels.forEach((label, index) => { label.id ||= `${editor.id}_label_${index}` })
    if (labels.length) editor.setAttribute("aria-labelledby", labels.map(label => label.id).join(" "))
  }
})
