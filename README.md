рестарт деплоя после обновления:

```sh
kubectl rollout restart deployment/server-print-deployment
```
```sh
kubectl get po
```
```sh
docker build -t gimmyhat/efgi-serv-print-257:latest .
```
```sh
docker push gimmyhat/efgi-serv-print-257:latest
```
```sh
kubectl apply -f server-print-deployment.yaml
```

http://172.27.239.23:30001/