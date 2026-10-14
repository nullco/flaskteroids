from config.environment import application as app

if __name__ == '__main__':
    app.run(debug=app.env.development)
