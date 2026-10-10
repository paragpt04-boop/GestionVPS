# Firma Android

GitHub Actions compila `app-release-unsigned.apk` y el APK debug. La versión entregada al propietario se firma fuera de GitHub con una identidad release propia; ninguna clave ni contraseña está en la APK o el repositorio.

La identidad de esta instalación está respaldada en `/root/gestionvps-android-signing/` en Miami, con acceso exclusivo de root. Contiene el PKCS#12 cifrado, su contraseña en un archivo protegido y el certificado público. Mantener una copia adicional cifrada y conservar esta identidad para futuras actualizaciones. No adjuntar esa carpeta a incidencias ni publicarla como artefacto de Actions.

Huella SHA-256 del certificado de firma: `30dd2bcf85159b9723b149567ecf9c6d1d3851cbb6cc953945f633764270c078`.

Con JDK 17 y apksigner de Android Build Tools 35.0.0, en un entorno privado:

```sh
java -jar apksigner.jar sign --ks /ruta/privada/miami-release.p12 --ks-type PKCS12 --ks-key-alias miami --ks-pass file:/ruta/privada/password.txt --out GestionVPS-0.2.0.apk app-release-unsigned.apk
java -jar apksigner.jar verify --verbose --print-certs GestionVPS-0.2.0.apk
```

La contraseña se lee del archivo; no introducirla como argumento visible del proceso. La clave de firma Android es diferente de las claves SSH, WireGuard y de la CA HTTPS.

Para automatizar firma release en el futuro, usar un entorno protegido de Actions y secretos privados del repositorio. La compilación pública actual no recibe material de firma ni credenciales del VPS. El APK debug tiene una firma diferente: desinstalarlo antes de instalar la versión release si se probó previamente.
