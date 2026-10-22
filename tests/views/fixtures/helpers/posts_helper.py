class PostsHelper:
    def post_link(self, title):
        return self.link_to(self.greeting(title), self.root_path())

    def viewer_label(self):
        return self.viewer()

    def choice(self):
        return "posts"
