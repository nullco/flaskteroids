def register(importmap):
    importmap.enable_integrity()
    importmap.pin("application")
    importmap.pin("@hotwired/turbo", to="turbo.js")
    importmap.pin_all_from("app/javascript/lib", under="lib")
    importmap.pin("optional", preload=False)
