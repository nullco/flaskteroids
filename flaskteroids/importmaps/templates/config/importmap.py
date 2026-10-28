# Pin packages with bin/importmap pin PACKAGE.


def register(importmap):
    importmap.pin("application")
    importmap.pin("@hotwired/turbo", to="turbo.js")
