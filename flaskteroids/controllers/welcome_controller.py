import textwrap
from flaskteroids.controller import ActionController
from flaskteroids import __version__ as version


class WelcomeController(ActionController):

    def show(self):
        return textwrap.dedent(f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8">
                <title>Welcome to Flaskteroids</title>
                <style>
                  html, body {{
                    height: 100%;
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                  }}
                  .container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100%;
                  }}
                  .content {{
                    background: #fff;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    text-align: center;
                  }}
                  h1 {{
                    color: #333;
                  }}
                  p {{
                    color: #666;
                  }}
                  a {{
                    color: #007BFF;
                    text-decoration: none;
                  }}
                  a:hover {{
                    text-decoration: underline;
                  }}
                </style>
              </head>
              <body>
                <div class="container">
                  <div class="content">
                    <h1>Flaskteroids</h1>
                    <p>Version: {version}</p>
                  </div>
                </div>
              </body>
            </html>
        """)
