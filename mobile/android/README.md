# Portal Membro — Android

Projeto Gradle multi-módulo (Fase 0 do [plano Android](../../docs/plano-trabalho-android.md)).

| Módulo | Papel |
|---|---|
| `:portal-api` | Cliente HTTP, modelos, `SessionRepository` / `SecureTokenStore` |
| `:app` | Compose — tela de login (stub); flavors `dev` / `staging` / `prod` |

## Host de build e emulador (Ubuntu)

**Não use o Mac para emular.** Use o Linux na LAN:

| | |
|---|---|
| Host | `192.168.50.32` |
| Usuário | `pablo` |

### 1. Liberar SSH (console do Ubuntu, uma vez)

```bash
bash scripts/android/enable-ssh-ubuntu.sh
# ou: sudo apt install -y openssh-server && sudo systemctl enable --now ssh
```

Do Mac: `ssh pablo@192.168.50.32`

### 2. Instalar JDK + SDK + emulador

No Ubuntu, com o repositório clonado/sincronizado:

```bash
bash scripts/android/setup-ubuntu.sh
source ~/.bashrc
```

### 3. Build e instalar no emulador

```bash
cd mobile/android
cp local.properties.example local.properties   # confira sdk.dir
./gradlew :portal-api:test :app:assembleDevDebug

emulator -avd Portal_API35 -no-audio -no-boot-anim &
adb wait-for-device
adb install -r app/build/outputs/apk/dev/debug/app-dev-debug.apk
```

Base URL no flavor `dev`: `http://10.0.2.2:8000` (API no mesmo host Ubuntu).  
Se a API estiver no Mac (`192.168.50.16`):

```bash
./gradlew :app:assembleDevDebug -PportalApiBaseUrl=http://192.168.50.16:8000
```

## Flavors

| Flavor | Cleartext | API default |
|---|---|---|
| `dev` | sim (LAN / emulador) | `http://10.0.2.2:8000` |
| `staging` | não | `https://staging.example.org` |
| `prod` | não | `https://portal.example.org` |

## Critério Fase 0

`./gradlew :app:assembleDevDebug` gera o APK e, no emulador, abre a tela de login.

Login real (`client: "android"`) → Fase 1.
