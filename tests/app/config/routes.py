def register(route):
    route.get('/up/', to="flaskteroids/health#show")
    route.get('/users/', to="users#index")
    with route.resources('post'):
        route.resources('comment')
