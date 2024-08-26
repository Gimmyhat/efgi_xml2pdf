рестарт деплоя после обновления:

```sh
kubectl rollout restart deployment/server-print-deployment
```
```sh
kubectl get po
```
```sh
docker build -t geolirk.cr.cloud.ru/efgi-serv-print-257:latest .
```
```sh
docker push geolirk.cr.cloud.ru/efgi-serv-print-257:latest
```

http://172.27.239.23:30001/