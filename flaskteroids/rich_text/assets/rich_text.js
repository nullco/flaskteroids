import { configure, highlightCode } from "lexxy"

configure({ default: { remoteImages: false } })

const submissions = new WeakMap()

function editorsFor(form) {
  return Array.from(form.querySelectorAll("lexxy-editor[data-flaskteroids-rich-text]"))
}

function hasUploads(form) {
  return editorsFor(form).some(editor => editor.querySelector("progress, .attachment--error"))
}

function rememberSubmission(form, submitter) {
  if (form && (hasUploads(form) || editorsFor(form).some(editor => editor.validity.customError))) {
    submissions.set(form, submitter)
  }
}

function resumeSubmission(form) {
  if (!form || !submissions.has(form) || hasUploads(form)) return
  // Upload completion and Lexxy's native validity refresh happen separately.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!form.isConnected || hasUploads(form) || !submissions.has(form)) return
    if (editorsFor(form).some(editor => !editor.validity.valid)) return
    const submitter = submissions.get(form)
    submissions.delete(form)
    if (submitter?.isConnected) form.requestSubmit(submitter)
    else form.requestSubmit()
  }))
}

document.addEventListener("click", event => {
  const submitter = event.target.closest('button, input[type="submit"], input[type="image"]')
  if (submitter && ["submit", "image"].includes(submitter.type)) rememberSubmission(submitter.form, submitter)
}, true)

document.addEventListener("invalid", event => {
  if (event.target.matches("lexxy-editor[data-flaskteroids-rich-text]")) {
    const form = event.target.form
    if (form && !submissions.has(form)) rememberSubmission(form, null)
    resumeSubmission(form)
  }
}, true)

document.addEventListener("submit", event => {
  if (hasUploads(event.target)) {
    event.preventDefault()
    submissions.set(event.target, event.submitter)
  }
}, true)

document.addEventListener("lexxy:upload-end", event => {
  const editor = event.target.closest("lexxy-editor[data-flaskteroids-rich-text]")
  if (!editor || !event.detail.error) return
  submissions.delete(editor.form)
  let alert = editor.parentElement.querySelector("[data-rich-text-upload-error]")
  if (!alert) {
    alert = document.createElement("div")
    alert.setAttribute("data-rich-text-upload-error", "")
    alert.setAttribute("role", "alert")
    editor.after(alert)
  }
  alert.textContent = event.detail.error
})

document.addEventListener("lexxy:change", event => {
  const editor = event.target
  if (!editor.matches("lexxy-editor[data-flaskteroids-rich-text]")) return
  if (!editor.querySelector(".attachment--error")) {
    editor.parentElement.querySelector("[data-rich-text-upload-error]")?.remove()
  }
  resumeSubmission(editor.form)
})

document.addEventListener("turbo:load", () => highlightCode())
