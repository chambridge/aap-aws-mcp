# aap-aws-mcp
Prototyping AWS metered container product
## Summary
Based on the [metered container product sample](https://github.com/aws-samples/aws-marketplace-metered-container-product) this project prototypes a simple container that will be used to obtain unique host under management in the last hour and send the metered information to the AWS Marketplace.

## Development

To get started developing with aap-aws-mcp first clone a local copy of the git repository:
```
git clone https://github.com/chambridge/aap-aws-mcp.git
````

1. Copy `example.env` into a `.env`
2. Obtain database values and update the following in your `.env`:
```
DATABASE_HOST=localhost
DATABASE_PORT=15432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=postgres
```
3. Then project dependencies and a virtual environment can be created using :
```
pipenv install --dev
```
4. To activate the virtual environment run :
```
    pipenv shell
```
## Build and Deploy

To build the container image:
```
make build
```

To deploy a pod with the image login to your Kubernetes cluster and namepace:
```
kubectl apply -f pod.yaml
```
