const { exec } = require('child_process');

console.log('🚀 Iniciando Zabbix Proxy...');

// Executar Docker Compose
exec('docker-compose up -d', (error, stdout, stderr) => {
  if (error) {
    console.error('❌ Erro ao iniciar serviços:', error);
    process.exit(1);
  }
  
  console.log('✅ Serviços iniciados com sucesso!');
  console.log(stdout);
  
  // Manter o processo rodando
  console.log('📊 Zabbix Proxy está rodando na porta 10051');
});

// Tratamento de sinais para parar graciosamente
process.on('SIGINT', () => {
  console.log('\n🛑 Parando serviços...');
  exec('docker-compose down', () => {
    process.exit(0);
  });
}); 