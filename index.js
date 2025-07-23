const { exec } = require('child_process');

console.log('🚀 Iniciando Zabbix Proxy...');

// Primeiro fazer build das imagens
console.log('🔨 Fazendo build das imagens Docker...');
exec('docker-compose -f docker-compose.proxy.yml build', (buildError, buildStdout, buildStderr) => {
  if (buildError) {
    console.log('⚠️  Build falhou, tentando executar sem build...');
    console.log(buildError.message);
  } else {
    console.log('✅ Build concluído com sucesso!');
    console.log(buildStdout);
  }
  
  // Executar Docker Compose
  console.log('🚀 Iniciando serviços...');
  exec('docker-compose -f docker-compose.proxy.yml up -d', (error, stdout, stderr) => {
    if (error) {
      console.error('❌ Erro ao iniciar serviços:', error);
      process.exit(1);
    }
    
    console.log('✅ Serviços iniciados com sucesso!');
    console.log(stdout);
    
    // Manter o processo rodando
    console.log('📊 Zabbix Proxy está rodando na porta 10051');
    
    // Manter o container vivo
    setInterval(() => {
      console.log('💓 Zabbix Proxy ainda rodando...');
    }, 60000);
  });
});

// Tratamento de sinais para parar graciosamente
process.on('SIGINT', () => {
  console.log('\n🛑 Parando serviços...');
  exec('docker-compose -f docker-compose.proxy.yml down', () => {
    process.exit(0);
  });
}); 