import "@hotwired/turbo"
import { value } from "lib/example"

window.importmapResult = value
window.loadOptional = async () => (await import("optional")).default
