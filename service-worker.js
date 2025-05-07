// service-worker.js

// Este Service Worker vai apenas escutar por eventos push e mostrar notificações.
// Ele roda em segundo plano e não tem acesso direto ao DOM da sua página HTML.

console.log('Service Worker iniciado.');

// Evento disparado quando o servidor envia uma mensagem push
self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push recebido.');
    console.log(`[Service Worker] Dados do Push: "${event.data.text()}"`);

    // Tenta obter os dados da notificação do payload (mensagem enviada pelo servidor)
    const pushData = event.data ? event.data.json() : { title: 'Notificação Genérica', body: 'Mensagem padrão' };

    const title = pushData.title || 'Sua Notificação'; // Usa título do servidor ou padrão
    const options = {
        body: pushData.body || 'Sem conteúdo.', // Usa corpo do servidor ou padrão (este seria o texto do usuário)
        icon: 'icon-192x192.png', // Opcional: substitua pelo caminho de um ícone real
        badge: 'badge-72x72.png', // Opcional: substitua pelo caminho de um ícone para badges (mobile)
        // Você pode incluir mais opções aqui, como 'image', 'vibrate', 'actions', etc.
        data: { // Dados adicionais que podem ser úteis ao clicar na notificação
            url: pushData.url || '/', // Exemplo: URL para abrir ao clicar
        }
    };

    // Mostra a notificação para o usuário
    // event.waitUntil() garante que o service worker não 'morra' antes da notificação ser exibida
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Evento disparado quando o usuário clica em uma notificação
self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notificação clicada.');

    const clickedNotification = event.notification;
    const primaryAction = event.action; // Ação clicada (se houver botões na notificação)
    const notificationData = clickedNotification.data; // Dados que você incluiu nas opções da notificação

    clickedNotification.close(); // Fecha a notificação após o clique

    // Faça algo dependendo da ação ou dados (ex: abrir uma janela/tab)
    if (primaryAction) {
        console.log(`[Service Worker] Ação clicada: ${primaryAction}`);
    } else {
        console.log('[Service Worker] Notificação clicada sem ação específica.');
        // Exemplo: Abrir uma URL quando a notificação principal é clicada
        const pageUrl = notificationData.url || '/'; // Pega a URL dos dados ou usa a raiz

        event.waitUntil(
            clients.openWindow(pageUrl)
        );
    }
});

// Opcional: Evento disparado quando a notificação é fechada (pelo sistema ou usuário)
self.addEventListener('notificationclose', function(event) {
    console.log('[Service Worker] Notificação fechada.');
});

// Outros eventos do Service Worker (install, activate, fetch, etc.) podem ser adicionados aqui