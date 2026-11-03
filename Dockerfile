FROM python:3.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive ANDROID_HOME=/opt/android-sdk GRADLE_BIN=/opt/gradle/bin/gradle
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk-headless unzip fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN python -c "import urllib.request; urllib.request.urlretrieve('https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip','/tmp/android.zip'); urllib.request.urlretrieve('https://services.gradle.org/distributions/gradle-8.13-bin.zip','/tmp/gradle.zip')" \
    && mkdir -p /opt/android-sdk/cmdline-tools /opt/gradle \
    && unzip -q /tmp/android.zip -d /tmp/android-cli \
    && mv /tmp/android-cli/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && unzip -q /tmp/gradle.zip -d /opt \
    && cp -a /opt/gradle-8.13/. /opt/gradle/ \
    && yes | /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null \
    && /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager 'platforms;android-36' 'build-tools;36.0.0' 'platform-tools' \
    && rm -f /tmp/android.zip /tmp/gradle.zip
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "90", "server:app"]
