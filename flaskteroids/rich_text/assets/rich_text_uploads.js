// Lexxy's DirectUpload transport contract, backed by Flaskteroids' authorized
// multipart endpoint. This module does not implement the Active Storage API.
export class DirectUpload {
  constructor(file, url, delegate) {
    this.file = file
    this.url = url
    this.delegate = delegate
  }

  create(callback) {
    const request = new XMLHttpRequest()
    request.open("POST", this.url)
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content
    if (!csrf) {
      callback("Missing CSRF token. Reload the form and try again.")
      return
    }
    request.setRequestHeader("X-CSRF-TOKEN", csrf)
    this.delegate?.directUploadWillStoreFileWithXHR?.(request)
    let completed = false
    const finish = (error, blob) => {
      if (completed) return
      completed = true
      callback(error, blob)
    }
    request.addEventListener("error", () => finish("Upload failed. Try again."))
    request.addEventListener("abort", () => finish("Upload cancelled."))
    request.addEventListener("load", () => {
      if (request.status !== 201) return finish("Upload failed. Remove the attachment and try again.")
      let blob
      try { blob = JSON.parse(request.responseText) } catch { return finish("Invalid upload response.") }
      if (!blob || typeof blob.attachable_sgid !== "string" || typeof blob.signed_id !== "string" || typeof blob.url !== "string") {
        return finish("Invalid upload response.")
      }
      finish(null, blob)
    })
    const body = new FormData()
    body.append("file", this.file)
    request.send(body)
  }
}
