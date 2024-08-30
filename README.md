рестарт деплоя после обновления:

```sh
kubectl rollout restart deployment/server-print-deployment-dev
```
```sh
kubectl get po
```
```sh
docker build -t gimmyhat/efgi-serv-print-257-dev:latest .
```
```sh
docker push gimmyhat/efgi-serv-print-257-dev:latest
```
```sh
kubectl apply -f server-print-deployment-dev.yaml
```

http://172.27.239.23:30001/