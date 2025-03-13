class Redirect(Exception):

    def __init__(self, response, *args):
        super().__init__(*args)
        self.response = response
