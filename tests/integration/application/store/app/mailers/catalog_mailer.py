from app.mailers.application_mailer import ApplicationMailer

from flaskteroids.mailer import helper, helper_method


class CatalogMailer(ApplicationMailer):
    helper("application")
    helper_method("_catalog_title")

    def notice(self):
        self.title = "Catalog for readers"
        return self.mail(to="reader@example.com", subject="Catalog")

    def _catalog_title(self, prefix, *, suffix):
        return f"{prefix}: {self.title}{suffix}"
