class CatalogHelper:
    def catalog_heading(self):
        verb = "Manage" if self.is_authenticated() else "Browse"
        return f"{verb} {self.application_name()}"

    def catalog_link(self):
        return self.link_to(self.catalog_heading(), self.products_path())
