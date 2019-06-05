#!/usr/bin/env python
# -*- coding: utf-8 -*-
import glib
import os
import signal
import urllib2
import json
import subprocess
import time
import threading
import logging

logging.basicConfig(filename='app.log', level=logging.DEBUG)

from pyudev import Context, Monitor

comandosSessaoX = [
	['xsetroot', '-cursor_name', 'X_cursor'],
	['xset', '-dpms'],
	['xset', 's', '0', '0'],
	['xset', 's', 'noblank'],
	['xset', 's', 'off'],
	['xset', '-q']
]

comandosSeat = [
	['xset', '-dpms',],
	['xset', 's', '0', '0'],
	['xset', 's', 'noblank'],
	['xset', 's', 'off'],
	['xset', '-q']
]

lockDevices = threading.Lock()

def obtemMac():
	try:
		meuMac = os.popen('cat /sys/class/net/$(ip route show default | awk \'/default/ {print $5}\')/address').read().strip()
		print len(meuMac)
		if(meuMac != None and len(meuMac) == 17):
			return meuMac
	except:
		return None
	return None
def obterJson(meuMac):
	try:
		jsonTexto = urllib2.urlopen("http://10.66.161.11/thinstation/scripts_bash/inicializar.php?python=1&enderecoMac="+meuMac).read()
		return jsonTexto
	except:
		return None

def matar_pid(pid):
	if(pid != None):
		#os.kill(pid, signal.SIGTERM)
		subprocess.call(['kill', str(pid)])

def esperar_pid(pid):
	args = ['wait', str(pid)]
	proc = subprocess.Popen(args, shell=True)
	proc.wait()

def obter_todos_os_dispositivos_deste_usb(usb):
	with lockDevices:
		if(usb != None):
			cmd = 'grep --only-matching ' + str(usb) + '/[^/]*/[^/]* /proc/bus/input/devices'
			resultado = os.popen(cmd).read().strip()
			if(len(resultado) <= 0):
				return None
			return resultado.split('\n')
	return None

def obter_evento_por_dispositivo(dispositivo):
	with lockDevices:
		if(dispositivo != None):
			cmd = "grep -A2 " + dispositivo + " /proc/bus/input/devices | grep 'H: Handlers=' | grep --only-matching -e 'event[0-9]*'"
			resultado = os.popen(cmd).read().strip()
			if(len(resultado) <= 0):
				resultado = None
			return resultado
	return None

def obter_handlers_do_dispositivo(dispositivo):
	with lockDevices:
		if(dispositivo != None):
			cmd = "grep -A2 " + dispositivo + " /proc/bus/input/devices | grep 'H: Handlers='"
			resultado = os.popen(cmd).read().strip()
			if(len(resultado) <= 0):
				resultado = None
			return resultado
	return None

class EstadoThread:
	NOVO = 0
	REDETECTAR_DISPOSITIVOS = 1
	REDETECTAR_DISPOSITIVOS_LEVE = 2
	PROBLEMA = 3
	TUDO_OK = 4
	listaString = ['NOVO', 'REDETECTAR_DISPOSITIVOS', 'REDETECTAR_DISPOSITIVOS_LEVE', 'PROBLEMA', 'TUDO OK']

class ThreadSeat(threading.Thread):
	def __init__(self, seat):
		threading.Thread.__init__(self)
		self.seat = seat
		self.yadPid = None

	def run(self):
		try:
			while(self.seat.sair != True):
				print "Thread seat " + str(self.seat.numero) + " estado: " + self.seat.obterEstadoString()
				if(self.seat.estado == EstadoThread.NOVO):
					self.seat.mudarEstado(EstadoThread.REDETECTAR_DISPOSITIVOS)
				elif(self.seat.estado == EstadoThread.REDETECTAR_DISPOSITIVOS):
					self.seat.desligaTela()
					self.seat.atualizarEventosDosDispositivos()
				elif(self.seat.estado == EstadoThread.REDETECTAR_DISPOSITIVOS_LEVE):
					self.seat.atualizarEventosDosDispositivos()
				elif(self.seat.estado == EstadoThread.PROBLEMA):
					if(self.seat.pidX == None):
						self.seat.iniciaTela()
					self.seat.exibeAviso()
				elif(self.seat.estado == EstadoThread.TUDO_OK):
					if(self.seat.pidX == None):
						self.seat.iniciaTela()
					self.seat.iniciaRDP()
				else:
					logging.error('Estado inválido para a seat ' + str(self.seat.numero) + ": " + str(self.seat.obterEstado()) )
					self.seat.estado = EstadoThread.NOVO

			self.seat.desligaTela()
		except:
			self.seat.desligaTela()
			logging.exception('')


class Seat:
	def finalizarQualquerAviso(self):
		if(self.yadPid != None):
			matar_pid(self.yadPid)
		self.yadPid = None
	def exibeAviso(self):
		args = ['yad', '--center', '--image', 'dialog-question', '--title', 'Atencao', '--text', str(self.problema)]
		proc = subprocess.Popen(args, env={"DISPLAY":self.tela_virtual})
		self.yadPid = proc.pid
		proc.wait()
		self.yadPid = None
	def mudarEstado(self, estadoNovo):
		with self.lockEstado:
			logging.warning('Mudando estado da seat ' + str(self.numero) + ' de ' + self.obterEstadoString() + ' para ' + EstadoThread.listaString[estadoNovo] )
			self.estado = estadoNovo
	def obterEstado(self):
		return self.estado
	def obterEstadoString(self):
		return EstadoThread.listaString[self.estado]
	def resetarDispositivos(self):
		self.mouse_evento = None
		self.teclado_evento = None
		self.problema = []
	def __init__(self, numero, teclado, mouse, servidor, usuario, senha, disp_entrada):
		self.estado = EstadoThread.NOVO
		self.lockDispositivo = threading.Lock()
		self.lockEstado = threading.Lock()
		self.lockXephyr = threading.Lock()
		self.lockRedetectarDisp = threading.Lock()
		self.yadPid = None
		self.pidX = None
		self.pidRDP = None
		self.mouse = mouse
		self.teclado = teclado
		self.numero = numero
		self.servidor = servidor
		self.usuario = usuario
		self.senha = senha
		self.disp_entrada = disp_entrada
		self.tela_real = ':0.'+str(self.numero)
		self.tela_virtual = ':'+str(self.numero+1)
		self.arquivoX_tela_virtual =  '/tmp/.X' + str(self.numero+1) + '-lock'
		self.problema = []
		self.sair = False
	def atualizarEventosDosDispositivos(self):
		logging.info('Atualizando eventos dos dispositivos da seat '+ str(self.numero))
		self.resetarDispositivos()
		self.mouse_evento = obter_evento_por_dispositivo(self.mouse)
		if(self.mouse_evento == None):
			self.problema.append("Mouse nao encontrado.")
		logging.info('Mouse:seat ' + str(self.numero) + ':evento ' + str(self.mouse_evento))
		self.teclado_evento = obter_evento_por_dispositivo(self.teclado)
		if(self.teclado_evento == None):
			self.problema.append("Teclado nao encontrado.")
		logging.info('Teclado:seat ' + str(self.numero) + ':evento ' + str(self.teclado_evento))

		if(len(self.problema) <= 0):
			self.mudarEstado(EstadoThread.TUDO_OK)
		else:
			self.mudarEstado(EstadoThread.PROBLEMA)

	def remover_dispositivo(self, tipo, potencialDispositivo):
		if(tipo == None):
			logging.warning('Dispositivo nao especificado foi removido, tentando identificar')
			if(potencialDispositivo == self.teclado):
				logging.warning('Acho que eh o teclado')
				tipo = 'teclado'
			elif(potencialDispositivo == self.mouse):
				logging.warning('Acho que eh o mouse')
				tipo = 'mouse'
			else:
				logging.error('Nao tenho ideia de qual dispositivo eh')
		if(tipo != None):
			logging.warning("remover_dispositivo(" + str(tipo) + ", " + potencialDispositivo + ")")
			if(self.disp_entrada != None):
				if(tipo == 'mouse'):
					self.mouse = None
				elif(tipo == 'teclado'):
					self.teclado = None
			self.redetectar_dispositivos_agora_leve()

	def adicionar_dispositivo(self, tipo, potencialDispositivo):
		logging.info("adicionar_dispositivo(" + str(tipo) + ", " + potencialDispositivo + ")")
		if(self.disp_entrada != None):
			if(tipo == 'mouse'):
				self.mouse = potencialDispositivo
			elif(tipo == 'teclado'):
				self.teclado = potencialDispositivo
		self.redetectar_dispositivos_agora()
		self.desligaX()

	def redetectar_dispositivos_agora_leve(self):
		with self.lockRedetectarDisp:
			self.mudarEstado(EstadoThread.REDETECTAR_DISPOSITIVOS_LEVE)
			self.finalizarQualquerAviso()
			self.desligaRDP()

	def redetectar_dispositivos_agora(self):
		with self.lockRedetectarDisp:
			self.mudarEstado(EstadoThread.REDETECTAR_DISPOSITIVOS)
			self.finalizarQualquerAviso()
			self.desligaRDP()

	def iniciaTela(self):
		with self.lockXephyr:
			if(self.pidX == None):
				args = ['Xephyr', '-br', '-ac', '-fullscreen', '-noreset', '-sw-cursor', self.tela_virtual]
				if(self.mouse_evento != None):
					args.append('-mouse')
					args.append('evdev,,device=/dev/input/'+self.mouse_evento)
				if(self.teclado_evento != None):
					args.append('-keybd')
					args.append('evdev,,device=/dev/input/'+self.teclado_evento)


				logging.info("Abrindo Xephyr para a seat " + str(self.numero))
				proc = subprocess.Popen(args, env={"DISPLAY": self.tela_real})
				self.pidX = proc.pid
				logging.info("Xephyr PID: " + str(self.pidX) + " seat " + str(self.numero))
				logging.info(args)

				#time.sleep(2)
				repete = True
				tentativas = 0
				tentativasMax = 200
				while(repete):
					pipe = subprocess.Popen(['xset', '-q'], env={"DISPLAY": self.tela_virtual}, stdout=subprocess.PIPE)
					out,err = pipe.communicate()

					logging.info("seat " + str(self.numero) + " " + str(out))
					logging.error("seat " + str(self.numero) + " " + str(err))

					if (out != None and "Keyboard" in out) or (err != None and "Keyboard" in err):
						repete = False
					else:
						repete = True
					tentativas+=1
					if(tentativas >= tentativasMax):
						raise Exception('Falha ao iniciar Seat apos ' + str(tentativasMax) + ' tentativas')
					#time.sleep(0.05)

				for comando in comandosSeat:
					proc = subprocess.Popen(comando, env={"DISPLAY": self.tela_virtual})
					proc.wait()
				#proc = subprocess.Popen(['xsetroot', '-solid', 'red'], env={"DISPLAY": self.tela_virtual})
			else:
				raise Exception('Nao se pode iniciar mais de um Xephyr por seat se já existe um aberto!')
	def iniciaRDP(self):
		if(self.pidX != None):
			proc = subprocess.Popen(['xfreerdp', '/v:'+self.servidor, '/u:'+self.usuario, '/d:ETECITAPEVA', '/p:'+self.senha, '/cert-ignore', '/rfx', '/network:lan', '+compression', '-z', '+auto-reconnect','/drive:Pendrives,/media/', '/f'], env={"DISPLAY": self.tela_virtual}, stdout=subprocess.PIPE)
			self.pidRDP = proc.pid
			out, err = proc.communicate()
			if(err != None and len(err) > 0):
				self.problema.append(err)
				self.mudarEstado(EstadoThread.PROBLEMA)
			self.pidRDP = None
	def desligaRDP(self):
		if(self.pidRDP != None):
			matar_pid(self.pidRDP)
			self.pidRDP = None
	def desligaX(self):
		with self.lockXephyr:
			logging.info('Matando Xephyr da seat ' + str(self.numero))
			if(self.pidX != None):
				matar_pid(self.pidX)
				time.sleep(0.05)
				#esperar_pid(self.pidX)
				self.pidX = None
				logging.info('Matança do Xephyr da seat ' + str(self.numero) + ' OK')
			else:
				logging.warning('Xephyr da seat '+ str(self.numero) +' inexistente...')
	def desligaTela(self):
		self.finalizarQualquerAviso()
		self.desligaRDP()
		self.desligaX()

class ThreadEventos(threading.Thread):
	def __init__(self, sessaoMultiseat):
		threading.Thread.__init__(self)
		self.sessaoMultiseat = sessaoMultiseat
		self.loop = glib.MainLoop()

	def finalizaMainLoop(self):
		self.loop.quit()

	def run(self):
		try:
			try:
				from pyudev.glib import MonitorObserver

				def device_event(observer, device):
					self.sessaoMultiseat.evento_dispositivo(device.action, device.device_path)
			except:
				from pyudev.glib import GUDevMonitorObserver as MonitorObserver

				def device_event(observer, action, device):
					self.sessaoMultiseat.evento_dispositivo(action, device.device_path)

			context = Context()
			monitor = Monitor.from_netlink(context)

			#monitor.filter_by(subsystem='usb');
			observer = MonitorObserver(monitor)

			observer.connect('device-event', device_event)
			monitor.start()

			self.loop.run()
		except:
			logging.exception('')

class SessaoMultiseat:
	def __init__(self):
		self.seats = []
		self.threadEventos = ThreadEventos(self)
		self.jsonResultante = None
	def carregaDados(self):
		while True:
			meuMac=obtemMac()
			if(meuMac != None):
				break
			else:
				print("Placa de rede nao encontrada, o cabo de rede está OK?")
				timer.sleep(1)
				continue

		while True:
			jsonTexto=obterJson(meuMac)
			if(jsonTexto != None):
				break
			else:
				print("Falha ao carregar configuracoes do servidor para este terminal, o cabo de rede está OK?")
				timer.sleep(1)
				continue

		self.jsonResultante = json.loads(jsonTexto)
	def inicializaX(self):
		env={"DISPLAY":":0"}
		repete = True
		proc = subprocess.Popen(['xsetroot', '-solid', 'green'], env=env)
		for comando in comandosSessaoX:
			proc = subprocess.Popen(comando, env=env)
			proc.wait()
	def inicializaSeats(self):
		seatNum = 0
		for valor in self.jsonResultante['seats']:
			seat = Seat(seatNum, valor.get('teclado', None), valor.get('mouse', None), valor['servidor']['nome'], valor['usuario'], 'daj2009@', valor.get('disp_entrada', None))
			threadSeat = ThreadSeat(seat)
			self.seats.append(threadSeat)
			seatNum = seatNum+1

		for seatThread in self.seats:
			if(seatThread.seat.disp_entrada != None):
				logging.info("Detectando Dispositivos USB de " + seatThread.seat.disp_entrada + " para a seat " + str(seatThread.seat.numero))
				dispositivosUsb = obter_todos_os_dispositivos_deste_usb(seatThread.seat.disp_entrada)
				if(dispositivosUsb != None):
					for dispositivoUsb in dispositivosUsb:
						logging.info("Adicionando USB " + dispositivoUsb)
						self.evento_dispositivo('add', dispositivoUsb)

		for seatThread in self.seats:
			seatThread.start()
	def inicializa(self):
		self.carregaDados()
		self.inicializaX()
		self.inicializaSeats()
		self.threadEventos.start()
	def desligaTudo(self):
		self.threadEventos.finalizaMainLoop()
		for threadSeat in self.seats:
			threadSeat.seat.sair = True
			threadSeat.seat.desligaTela()
	def evento_dispositivo(self, action, device_path):
		logging.info('evento_dispositivo' + ' acao: ' + action + " device_path" + device_path)
		if(action == 'remove' or action == 'add'):
			for seatThread in self.seats:
				if((seatThread.seat.disp_entrada != None and seatThread.seat.disp_entrada in device_path) or (seatThread.seat.teclado != None and seatThread.seat.teclado in device_path) or (seatThread.seat.mouse != None and seatThread.seat.mouse in device_path)):
					with seatThread.seat.lockDispositivo:
						if(seatThread.seat.disp_entrada != None):
							potencialDispositivo = device_path[device_path.rindex('/')+1:]
							if(":" in potencialDispositivo):
								logging.info("Potencial dispositivo usb (" +potencialDispositivo+ ") para a seat " + str(seatThread.seat.numero))
								tipo = None
								handlers = obter_handlers_do_dispositivo(potencialDispositivo)
								if(handlers != None):
									if("mouse" in handlers):
										tipo = "mouse"
									elif("leds" in handlers and "kbd" in handlers):
										tipo = "teclado"
									if(tipo != None):
										if(action == 'add'):
											seatThread.seat.adicionar_dispositivo(tipo, potencialDispositivo)
										else:
											seatThread.seat.remover_dispositivo(tipo, potencialDispositivo)
								else:
									if(action == "remove"):
										seatThread.seat.remover_dispositivo(None, potencialDispositivo)
						break;


try:
	glib.threads_init()
	s = SessaoMultiseat()
	s.inicializa()
	time.sleep(35)
	s.desligaTudo()
except:
	logging.exception('')

