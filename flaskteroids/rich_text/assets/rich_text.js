const richTextUploads = new WeakMap()
const richTextSubmissions = new WeakMap()

function uploadsFor(editor) {
  if (!richTextUploads.has(editor)) richTextUploads.set(editor, new Map())
  return richTextUploads.get(editor)
}

function uploadError(editor, message) {
  let alert = editor.parentElement.querySelector("[data-rich-text-upload-error]")
  if (!alert) {
    alert = document.createElement("div")
    alert.setAttribute("data-rich-text-upload-error", "")
    alert.setAttribute("role", "alert")
    editor.after(alert)
  }
  alert.textContent = message
  editor.dispatchEvent(new CustomEvent("rich-text-upload-error", { bubbles: true, detail: { message } }))
}

function hasPendingUploads(form) {
  return Array.from(form.querySelectorAll("trix-editor")).some(editor => uploadsFor(editor).size > 0)
}

function resumeSubmission(form) {
  if (form && form.isConnected && richTextSubmissions.has(form) && !hasPendingUploads(form)) {
    const submitter = richTextSubmissions.get(form)
    richTextSubmissions.delete(form)
    if (submitter?.isConnected) form.requestSubmit(submitter)
    else form.requestSubmit()
  }
}

document.addEventListener("submit", event => {
  if (hasPendingUploads(event.target)) {
    event.preventDefault()
    richTextSubmissions.set(event.target, event.submitter)
  }
}, true)

document.addEventListener("trix-file-accept", event => {
  if (event.target.hasAttribute("data-flaskteroids-rich-text") && !event.target.dataset.uploadUrl) {
    event.preventDefault()
  }
})

document.addEventListener("trix-attachment-add", event => {
  const editor = event.target
  if (!editor.hasAttribute("data-flaskteroids-rich-text")) return
  const attachment = event.attachment
  const file = attachment.getFile()
  if (!file) {
    if (!attachment.getAttributes().sgid) attachment.remove()
    return
  }
  const form = editor.closest("form")
  const csrf = form?.querySelector('input[name="csrf_token"]')?.value
  if (!form || !csrf || !editor.dataset.uploadUrl) {
    uploadError(editor, "This editor cannot upload files. Reload the form and try again.")
    attachment.remove()
    return
  }
  const request = new XMLHttpRequest()
  const entry = { request, cancelled: false }
  uploadsFor(editor).set(attachment, entry)
  request.open("POST", editor.dataset.uploadUrl)
  request.setRequestHeader("X-CSRF-TOKEN", csrf)
  request.upload.addEventListener("progress", progress => {
    if (progress.lengthComputable) attachment.setUploadProgress(progress.loaded / progress.total * 100)
  })
  const failed = () => {
    if (entry.cancelled) return
    uploadError(editor, "Upload failed. Remove the attachment and try again.")
    richTextSubmissions.delete(form)
  }
  request.addEventListener("error", failed)
  request.addEventListener("abort", failed)
  request.addEventListener("load", () => {
    if (entry.cancelled) return
    if (request.status !== 201) return failed()
    let attributes
    try { attributes = JSON.parse(request.responseText) } catch { return failed() }
    if (!attributes.sgid) return failed()
    attachment.setAttributes(attributes)
    attachment.setUploadProgress(100)
    uploadsFor(editor).delete(attachment)
    resumeSubmission(form)
  })
  const body = new FormData()
  body.append("file", file)
  request.send(body)
})

document.addEventListener("trix-attachment-remove", event => {
  const editor = event.target
  if (!editor.hasAttribute("data-flaskteroids-rich-text")) return
  const pending = uploadsFor(editor).get(event.attachment)
  if (pending) {
    pending.cancelled = true
    pending.request.abort()
    uploadsFor(editor).delete(event.attachment)
  }
  if (!uploadsFor(editor).size) {
    editor.parentElement.querySelector("[data-rich-text-upload-error]")?.remove()
  }
  resumeSubmission(editor.closest("form"))
})

document.addEventListener("trix-initialize", event => {
  const editor = event.target
  if (!editor.hasAttribute("data-flaskteroids-rich-text")) return
  if (!editor.dataset.uploadUrl) {
    editor.toolbarElement.querySelector('[data-trix-button-group="file-tools"]')?.remove()
  }
  if (!editor.hasAttribute("aria-label") && !editor.hasAttribute("aria-labelledby")) {
    const labels = Array.from(document.querySelectorAll("label")).filter(label => label.htmlFor === editor.id)
    labels.forEach((label, index) => { label.id ||= `${editor.id}_label_${index}` })
    if (labels.length) editor.setAttribute("aria-labelledby", labels.map(label => label.id).join(" "))
  }
})
