// public/script.js

const notificationText = document.getElementById('notificationText');
const repeatCountInput = document.getElementById('repeatCount');
const intervalTimeInput = document.getElementById('intervalTime');
const startButton = document.getElementById('startButton');
const statusSpan = document.getElementById('status');

// --- Sua Chave Pública VAPID ---
// Copiada da chave que você gerou
const applicationServerKey = 'BAqiLyUbWPICFTpW4Gf_RpTKWAws6LxDy7Lu3Ch4bUb0OYooef7HG0rAVdLT32qAbtVbszdsIBJb5SjwQBFTm9M';


// --- Funções de Suporte para Web Push ---

// Converte uma string base64url para Uint8Array
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Registra o Service Worker
async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
        statusSpan.textContent = 'Erro: Este navegador não suporta Service Worker.';
        return null;
    }

    try {
        // O caminho do Service Worker é relativo à raiz do DOMAIN, não à pasta atual
        // Como o app.py serve da pasta 'public', o Service Worker na raiz de 'public'
        // é acessado como /service-worker.js
        const registration = await navigator.serviceWorker.register('./service-worker.js');
        statusSpan.textContent = 'Service Worker registrado com sucesso.';
        console.log('Service Worker registrado:', registration);
        return registration;
    } catch (error) {
        statusSpan.textContent = `Erro ao registrar o Service Worker: ${error}`;
        console.error('Service Worker registration failed:', error);
        return null;
    }
}

// Assina o usuário para Web Push
async function subscribeUserToPush(registration) {
    if (!('PushManager' in window)) {
        statusSpan.textContent = 'Erro: Este navegador não suporta Push Notifications.';
        return null;
    }

    try {
        // Verifica se já existe uma assinatura
        const existingSubscription = await registration.pushManager.getSubscription();
        if (existingSubscription) {
            console.log('Assinatura Push existente encontrada:', existingSubscription);
            statusSpan.textContent = 'Já assinados para Push Notifications.';
            return existingSubscription;
        }

        // Se não existir, cria uma nova assinatura
        statusSpan.textContent = 'Criando nova assinatura Push...';
        const subscribeOptions = {
            userVisibleOnly: true, // Deve ser true para notificações visíveis
            applicationServerKey: urlBase64ToUint8Array(applicationServerKey),
        };
        const pushSubscription = await registration.pushManager.subscribe(subscribeOptions);
        statusSpan.textContent = 'Assinatura Push criada com sucesso.';
        console.log('Nova Assinatura Push:', pushSubscription);
        return pushSubscription;

    } catch (error) {
        statusSpan.textContent = `Erro ao criar assinatura Push. Certifique-se de que as permissões de Notificação e Push foram concedidas. Detalhes: ${error}`;
        console.error('Failed to subscribe the user:', error);
        return null;
    }
}

// Envia a assinatura e as preferências para o seu servidor
async function sendSubscriptionToServer(subscription, prefs) {
    // --- ESTE É ONDE VOCÊ INTERAGE COM SEU BACKEND PYTHON ---
    // Substitua '/save-subscription-and-prefs' pela URL real do seu endpoint no servidor Flask
    // Como o backend Flask está servindo na raiz '/', o endpoint será /save-subscription-and-prefs
    const serverEndpoint = '/save-subscription-and-prefs';

    try {
        statusSpan.textContent = 'Enviando dados para o servidor...';
        const response = await fetch(serverEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                subscription: subscription,
                preferences: prefs, // Inclui texto, repetições, intervalo em segundos
            }),
        });

        if (response.ok) {
            // Servidor retornou sucesso (status 2xx)
            const result = await response.json();
            statusSpan.textContent = 'Configuração salva no servidor!';
            console.log('Resposta do Servidor:', result);
        } else {
            // Servidor retornou um erro (status 4xx ou 5xx)
            const errorText = await response.text(); // Tenta ler a resposta de erro
            statusSpan.textContent = `Erro do servidor (${response.status}): ${response.statusText} - ${errorText}`;
            console.error('Erro do Servidor:', response.status, response.statusText, errorText);
             // Se o servidor retornar 409 Conflict, pode significar que a assinatura já existe com outra config, etc.
        }
    } catch (error) {
        statusSpan.textContent = `Erro de comunicação: Não foi possível conectar ao servidor. ${error}`;
        console.error('Erro de Fetch:', error);
    }
}


// --- Lógica Principal ---

async function handleStartButtonClick() {
    startButton.disabled = true;
    statusSpan.textContent = 'Iniciando processo de configuração...';

    // 1. Verificar suporte das APIs
    if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
        statusSpan.textContent = 'Erro: Seu navegador não suporta Notificações ou Push API completamente.';
        startButton.disabled = false;
        return;
    }

    // 2. Verificar status da permissão de Notificação
    if (Notification.permission === 'denied') {
        statusSpan.textContent = 'Permissão de notificação negada. Por favor, habilite nas configurações do navegador.';
        startButton.disabled = false;
        return;
    }

     // 3. Pedir permissão de Notificação se não concedida
     if (Notification.permission === 'default') {
        statusSpan.textContent = 'Solicitando permissão para notificações...';
        const notificationPermission = await Notification.requestPermission();
         if (notificationPermission !== 'granted') {
             statusSpan.textContent = `Permissão de notificação não concedida (${notificationPermission}).`;
             startButton.disabled = false;
             return;
         }
         statusSpan.textContent = 'Permissão de notificação concedida.';
     } else {
          statusSpan.textContent = `Permissão de notificação já em '${Notification.permission}'.`;
     }


    // 4. Registrar o Service Worker
    const registration = await registerServiceWorker();
    if (!registration) {
        startButton.disabled = false;
        return;
    }

    // 5. Assinar para Push Notifications (ou obter assinatura existente)
    const subscription = await subscribeUserToPush(registration);
     if (!subscription) {
         // Erro na assinatura ou usuário negou a permissão de Push
         startButton.disabled = false;
         return;
     }

    // 6. Obter as preferências do usuário
    const message = notificationText.value.trim();
    const count = parseInt(repeatCountInput.value);
    const intervalSeconds = parseInt(intervalTimeInput.value); // Intervalo em segundos

     // Validação dos inputs
     if (message === '') {
         statusSpan.textContent = 'Por favor, digite o texto da notificação.';
          startButton.disabled = false;
         return;
     }
     if (isNaN(count) || count <= 0) {
         statusSpan.textContent = 'Por favor, insira um número de repetições válido (> 0).';
          startButton.disabled = false;
         return;
     }
      if (isNaN(intervalSeconds) || intervalSeconds < 5) { // Intervalo mínimo razoável
         statusSpan.textContent = 'Por favor, insira um intervalo de tempo válido (mínimo 5 segundos).';
          startButton.disabled = false;
         return;
     }


    const userPreferences = {
        message: message,
        repeatCount: count,
        intervalSeconds: intervalSeconds,
        // Você pode adicionar outras preferências aqui
    };

    // 7. Enviar assinatura e preferências para o servidor
    // O servidor será responsável por armazenar isso e agendar os envios push.
    await sendSubscriptionToServer(subscription, userPreferences);

    startButton.disabled = false; // Reabilita o botão no final do processo de envio
}

// --- Event Listeners ---
startButton.addEventListener('click', handleStartButtonClick);


// --- Inicialização ao carregar a página ---
window.addEventListener('load', async () => {
     // Verifica o status inicial das APIs
    if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
         statusSpan.textContent = 'Seu navegador pode não suportar Notificações/Push API.';
    } else {
         statusSpan.textContent = `Status Notificação: ${Notification.permission}`;
         // Você pode adicionar lógica aqui para verificar se já tem uma assinatura Push
         // usando navigator.serviceWorker.ready.then(reg => reg.pushManager.getSubscription())
         // e talvez mostrar um status diferente ou permitir atualizar a config.
     }
});