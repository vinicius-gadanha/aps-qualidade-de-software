// AgendaLab 2.0 - pede confirmação antes de enviar formulários que excluem dados.
document.addEventListener("submit", function (evento) {
  var mensagem = evento.target.getAttribute("data-confirmar");
  if (mensagem && !window.confirm(mensagem)) {
    evento.preventDefault();
  }
});
