# CHANGELOG

<!-- version list -->

## v0.2.1 (2026-11-27)

### Bug Fixes

- **agi**: Não guardar a exceção do login que falhou
  ([`fc93823`](https://github.com/pedroct/stur-api/commit/fc938234731efaa8f068c0d383f6e837d09ed59f))

- **agi**: Um login por intervalo na verificação de acesso e espera depois de recusa
  ([`35564f1`](https://github.com/pedroct/stur-api/commit/35564f1e2e201c3183d831ebacb0d4b993799f6e))

- **cache**: Limitar o cache de resultados pelo total de linhas
  ([`3b08969`](https://github.com/pedroct/stur-api/commit/3b0896903d79c6436e38b6041b92e4415254e623))

- **consultas**: Limitar as consultas de período simultâneas
  ([`e1542f3`](https://github.com/pedroct/stur-api/commit/e1542f300db533eea480052bf54387b0c8bc50a9))

- **consultas**: Parar o trabalho de quem desiste do pedido
  ([`46bcf14`](https://github.com/pedroct/stur-api/commit/46bcf14ba4e45eafc0f83b8d53d66ead5613c1e6))

### Continuous Integration

- **release**: Reconstruir a imagem de uma tag já publicada
  ([`39925ec`](https://github.com/pedroct/stur-api/commit/39925ec4423049b072106cae42ce3ea221088274))

### Testing

- **consultas**: Deixar uma só chamada dentro do pytest.raises (python:S5778)
  ([`5ed9985`](https://github.com/pedroct/stur-api/commit/5ed9985ad7a473c1fd287ef8989e89e4095b3daf))


## v0.2.0 (2026-11-27)

### Bug Fixes

- **lancamentos**: Cada número de documento uma vez só
  ([`c809b35`](https://github.com/pedroct/stur-api/commit/c809b357042d234c0a90e1e98de868f70509d065))

### Features

- **reserva**: Resumo do serviço, saldos da reserva e detalhes dos lançamentos
  ([`1c74668`](https://github.com/pedroct/stur-api/commit/1c74668bbe80fe7f047924f29cf8630c496fb873))


## v0.1.0 (2026-11-25)

- Initial Release
