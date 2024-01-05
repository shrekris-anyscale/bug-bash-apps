from ray import serve

@serve.deployment(ray_actor_options={"num_cpus": 0})
class Hello:

    def __call__(self, *args):
        return "Hello world!"

app = Hello.bind()
