import yaml
import requests

controller_ip="10.20.12.116"
controller="http://"+controller_ip + ":8080"

class Alumno:
    def __init__(self, nombre, codigo, mac):
        self.nombre= nombre
        self.codigo = codigo
        self.mac = mac

class Curso:
    def __init__(self,codigo,estado,nombre,alumnos,ServidorCurso):
        self.codigo = codigo
        self.nombre= nombre
        self.estado= estado
        self.alumnos= alumnos
        self.ServidorCurso= ServidorCurso
    def agregar_alumno(self,alumno):
        self.alumnos.append(alumno)
    def remover_alumno(self,alumno):
        self.alumnos.remove(alumno)
    def agregar_servidores(self,servidor):
        self.ServidorCurso.append(servidor)


class Servidor:
    def __init__(self,nombre,ip,servicios):
        self.nombre= nombre
        self.ip= ip
        self.servicios= servicios

class Servicio:
    def __init__(self,nombre,protocolo,puerto):
        self.nombre= nombre
        self.protocolo= protocolo
        self.puerto= puerto



alumnos =[Alumno("","","")]
cursos = [Curso("","","","","")]
servidores = [Servidor("","","")]
exist_Data=False



def get_mac(hostip):
    global controller
    path= controller+"/wm/device/"
    resp=requests.get(path)
    resp= resp.json()
    for i in resp:
        if((hostip in i["ipv4"] )):
            return i["mac"][0]
    return "not found"

def get_attachement_points(host):
    global controller
    path= controller+"/wm/device/"
    resp=requests.get(path)
    resp= resp.json()
    for i in resp:
        if((host in i["mac"] ) or (host in i["ipv4"] )):
            return i["attachmentPoint"][0]["switchDPID"],i["attachmentPoint"][0]["port"]
    return "not found", "error"

def get_route(dpid_src,prt_src,dpid_dest,prt_dest):
    global controller
    path = controller+"/wm/topology/route/"+dpid_src+"/"+prt_src+"/"+dpid_dest+"/"+prt_dest+"/json"
    resp = requests.get(path).json()
    #resp = json.dumps(resp.json(),indent=4, sort_keys=True)
    ret={}
    x=0;
    for i in resp:
        ret[x]={"switch":i['switch'],"puerto":i['port']["portNumber"]}
        x+=1
    return ret

def push_flow(data):
    global controller
    path = controller+'/wm/staticflowpusher/json'
    resp=requests.post(path, json=data)
    if(str(resp.status_code)!="200"):
        raise Exception("No se ha podido conectar con el servidor")

def delete_flow(data):
    global controller
    path = controller+'/wm/staticflowpusher/json'
    resp=requests.delete(path, json=data)
    if(str(resp.status_code)!="200"):
        raise Exception("No se ha podido conectar con el servidor")



conexiones=[]
class Conexion:
    def __init__(self,alumno,servidor,servicio):
        global cursos,conexiones
        self.alumno=alumno
        self.servidor=servidor
        self.servicio=servicio
        for i in cursos:
            if(alumno in i.alumnos):
                for j in i.ServidorCurso:
                    if(servidor==j.serv and (servicio in j.permitidos)):
                        self.conn={"src":alumno.mac, "dst":servidor.ip}                         
                        self.stablish_conn()
                        return
        raise Exception("El alumno no se encuentra matriculado en un curso con los permisos para servicio")
    
    def stablish_conn(self):

        servermac= get_mac(self.servidor.ip)
        src_dpid,src_port = get_attachement_points(self.conn["src"])
        dst_dpid,dst_port= get_attachement_points(self.conn["dst"])
        route = get_route(src_dpid,str(src_port),dst_dpid,str(dst_port))
        name= self.alumno.codigo+"-"+self.servidor.nombre+"-"+self.servicio.nombre
        flows=[]
        for i in range(len(route)//2):
            index=i*2
            tmp = {
                "name":name+"-"+str(index)+"alsr",
                "switch": route[index]["switch"],
                "in_port": route[index]["puerto"],
                "priority":"1000",
                "active":"true",
                "eth_src": self.alumno.mac,
                "set_ipv4_dst": self.servidor.ip,
                "eth_type": "0x0800",
                "actions": "output="+str(route[index+1]["puerto"]),
            }

            tmp2 = {
                "name":name+str(index)+"sral",
                "switch": route[index]["switch"],
                "in_port": route[index+1]["puerto"],
                "priority":"1000",
                "active":"true",
                "eth_src": servermac,
                "eth_dst": self.alumno.mac,
                "actions": "output="+str(route[index]["puerto"]),
            }

            arp1= {
                "name":name+"-"+str(index)+"arpalsr",
                "switch": route[index]["switch"],
                "in_port": route[index]["puerto"],
                "priority":"1000",
                "active":"true",
                "eth_src": self.alumno.mac,
                "arp_tpa": self.servidor.ip,
                "eth_type": "0x0806",
                "actions": "output="+str(route[index+1]["puerto"]),
            }


            if(self.servicio.protocolo=="TCP"):
                tmp["tcp_dst"]=self.servicio.puerto
                tmp["ip_proto"]="0x06"
            elif(self.servicio.protocolo=="UDP"):
                tmp["udp_dst"]=self.servicio.puerto
                tmp["ip_proto"]="0x11"
            else:
                raise Exception("No se ha podido identificar el protocolo")
            flows.append(tmp)
            flows.append(tmp2)
            flows.append(arp1)
        self.flows = flows
        for i in flows:
            push_flow(i)

    def delete_conn(self):
        try:
            for i in self.flows:
                delete_flow(i)
        except Exception as e:
            print(e)
    

class ServidorCurso:
    def __init__(self,serv,permitidos):
        self.serv=serv
        self.permitidos= permitidos


def inputDeseado(msg,listaOpciones):
    while(True):
        x=input(msg)
        if(x in listaOpciones):
            return x
        print("!#### No es válido ####!")


def opcionesShow(opciones):
    c=1
    print("\n================Opciones Disponibles================")
    for i in opciones:
            print(str(c)+") "+i)
            c+=1

def listarAlumnos():
    global alumnos
    print("==================================Lista de alumnos==================================")
    for i in alumnos:
        print("-"+i.nombre+"\tCódigo:"+i.codigo)

def listarCursos():
    global cursos
    print("==================================Lista de cursos==================================")
    for i in cursos:
        print("-"+i.nombre+"\tCódigo:"+i.codigo+"\tEstado:"+i.estado)

def listarServidores():
    global servidores
    print("======================Lista de servidores======================")
    for i in servidores:
        print("-"+i.nombre+"\tIP:"+i.ip)

def encontrarAlumnoPorCod(codigo):
    global alumnos
    for i in alumnos:
        if(i.codigo==codigo):
            return i
    return 0

def encontrarServidorPorNombre(nombre):
    global servidores
    for i in servidores:
        if(i.nombre==nombre):
            return i
    return 0

def encontrarServicio(serv,nombre):
    for i in serv.servicios:
        if(i.nombre==nombre):
            return i
    return 0

def encontrarCursoPorCodigo(codigo):
    global cursos
    for i in cursos:
        if(i.codigo==codigo):
            return i,True
    return 0,False

def encontrarAlumnoPorCodigo(codigo):
    global alumnos
    for i in alumnos:
        if(i.codigo==codigo):
            return i,True
    return 0,False


class Menu():
    def __init__(self):
        pass
    def start(self):
        print("#######################################")
        print("Network Policy manager de la UPSM")
        print("#######################################")
        debeImprimir=True
        while(True):
            if(debeImprimir):
                opcionesShow(["Importar","Exportar","Cursos","Alumnos","Servidores","Políticas","Conexiones","Salir"])
                print("Puede volver en cualquier momento al menu con (z)")
            debeImprimir=True
            inp=inputDeseado("Ingrese opción: ",["1","2","3","4","5","6","7","8"])
            if(inp=="1"):
                self.importar()
            elif(inp=="2" and exist_Data):
                self.exportar()
            elif(inp=="3" and exist_Data):
                self.cursos()
            elif(inp=="4" and exist_Data):
                self.alumnos()
            elif(inp=="5" and exist_Data):
                self.servidores()
            elif(inp=="6" and exist_Data):
                self.politicas()
            elif(inp=="7" and exist_Data):
                self.conexiones()
            elif(inp=="8"):
                break
            else:
                print("No se ha importado ningún YAML")
                debeImprimir=False
                continue
    def importar(self):
        global alumnos,servidores,cursos, exist_Data
        alumnos=[]
        servidores=[]
        cursos=[]
        exist_Data=False;
        direccion=input("Ingrese la dirección del archivo: ")
        if(direccion=="z"):
            return
        try:
            with open(direccion,"r") as stream:
                data= yaml.safe_load(stream)
            for i in data["alumnos"]:
                alumno= Alumno(i["nombre"],str(i["codigo"]),i["mac"])
                alumnos.append(alumno)
            for i in data["servidores"]:
                x=[]
                for j in i["servicios"]:
                    x.append(Servicio(j["nombre"],j["protocolo"],str(j["puerto"])))
                servidores.append(Servidor(i["nombre"],i["ip"],x))

            for i in data["cursos"]:
                x=[]
                for j in i["alumnos"]:
                    x.append(encontrarAlumnoPorCod(str(j)))
                y=[]
                for j in i["servidores"]:
                    z=[]
                    serv = encontrarServidorPorNombre(j["nombre"])
                    for k in j["servicios_permitidos"]:
                        z.append(encontrarServicio(serv,k))
                    y.append(ServidorCurso(serv,z))
                cursos.append(Curso(i["codigo"],i["estado"],i["nombre"],x,y))
            exist_Data=True
            print("Importado con éxito")
        except Exception as e:
            print("Ha ocurrido un error y no se ha podido importa")


    def exportar(self):
        pass
    def cursos(self):
        global cursos
        opcionesShow(["Listar (-t) Todo (-s) Servidor-servicio ","Mostrar detalle", "Actualizar"])
        while(True):
            inp=input("Ingrese opción: ").strip()
            if(inp=="z"):
                return
            if(len(inp)==0):
                print("No se ha leido el input")
            elif(inp[0]=="1"):
                listainp = inp.split()
                if(len(listainp)>2 or len(listainp)==1):
                    print("!#### No es válido ####!")
                elif(listainp[1]=="-t"):
                    listarCursos();
                    break
                elif(listainp[1]=="-s"):
                    while(True):
                        servidorNombre= input("Ingrese el nombre del servidor (0) para listarlos: ")
                        if(servidorNombre=="z"):
                            return
                        servidor = encontrarServidorPorNombre(servidorNombre)
                        if(servidorNombre=="0"):
                            listarServidores();
                        elif(servidor!=0):
                            break
                        else:
                            print("No se ha encontrado ningún servidor")
                    while(True):
                        servicioNombre = input("Ingrese el nombre del servicio (0) para listar servicios: ")
                        if(servicioNombre=="z"):
                            return
                        if(servicioNombre=="0"):
                            print("================Servicios del servidor================")
                            for i in servidor.servicios:
                                print("Nombre: "+i.nombre+", Protocolo: "+i.protocolo+", Puerto: "+i.puerto)
                        else:
                            servicio= encontrarServicio(servidor,servicioNombre)
                            if(servicio==0):
                                print("No se ha encontrado el servicio")
                            else:
                                break
                    print("==============Lista de cursos con acceso a "+servidor.nombre+"-"+servicio.nombre+"============")
                    for i in cursos:
                        for j in i.ServidorCurso:
                            if(servidor == j.serv and (servicio in j.permitidos)):
                                print("Nombre: "+i.nombre+", Código: "+i.codigo+", Estado: "+i.estado)
                                break
                    break

                else:
                    print("!#### No es válido ####!")
                    continue

            elif(inp=="2"):
                while(True):
                    inp2= input("Indique el código del curso (0) para listar cursos\nCódigo: ")
                    if(inp2=="z"):
                        return
                    curso, existe = encontrarCursoPorCodigo(inp2)
                    if(inp2=="0"):
                        listarCursos()
                        continue
                    elif(existe):
                        print("------------------Detalles------------------")
                        print("Nombre: "+curso.nombre)
                        print("Código: "+curso.codigo)
                        print("Estado: "+curso.estado)
                        print("Alumnos:")
                        for i in curso.alumnos:
                            print("\t-Nombre: "+i.nombre)
                            print("\tCódigo: "+ i.codigo)
                            print("\tMAC: "+i.mac)
                        print("Servidores")
                        for i in curso.ServidorCurso:
                            print("\t-Nombre: "+i.serv.nombre)
                            print("\tIP: "+i.serv.ip)
                            print("\tServicios permitidos: ")
                            for k in i.permitidos:
                                print("\t\t-Nombre: "+k.nombre)
                                print("\t\tProtocolo: "+k.protocolo)
                                print("\t\tPuerto: "+k.puerto)
                        break
                    else:
                        print("No se ha encontrado ningún curso con ese código")
                        break
                break
            elif(inp=="3"):
                temp=inputDeseado("Desea (a)Agregar o (e)Elimnar a un alumno de un curso?\n",["a","e","z"])
                if(temp=="z"):
                    return
                while(True):
                    codigoCurso=input("Indique el código del curso, (0) para listar cursos: ")
                    if(codigoCurso=="z"):
                        return
                    if(codigoCurso=="0"):
                        listarCursos()
                    else:
                        curso, existe=encontrarCursoPorCodigo(codigoCurso)
                        if(existe):
                            break
                        else:
                            print("No existe el curso, vuelva a ingresar el codigo")

                while(True):
                    codigoAlumno=input("Indique el código del alumno (0) para listar alumnos: ")
                    if(codigoAlumno=="z"):
                        return
                    if(codigoAlumno=="0"):
                        listarAlumnos()
                    else:
                        alumno = encontrarAlumnoPorCod(codigoAlumno)
                        if(alumno != 0):
                            break
                        else:
                            print("No existe el alumno, vuelva a ingresar el codigo")

                if(temp=="a"):
                    if(alumno in curso.alumnos):
                        print("El alumno ya se encuentra registrado en el curso")
                    else:
                        curso.agregar_alumno(alumno)
                        print("Se ha agregado a",alumno.nombre,"al curso",curso.nombre)
                elif(temp=="e"):
                    if(alumno in curso.alumnos):
                        curso.remover_alumno(alumno)
                        print("Se ha eliminado a",alumno.nombre,"del curso",curso.nombre)
                    else:
                        print("El alumno no se encuentra en el curso")
                break
            else:
                print("No se ha ingresado una opción valida")

 
    def alumnos(self):
        opcionesShow(["Listar (-t) Todo, (-a) Año (indicar valor), (-c) Código de Curso (indicar valor)","Mostrar detalles","Crear alumno"])
        global alumnos
        global cursos
        while(True):
            inp = input("Indique la opción: ").strip()
            if(inp=="z"):
                return
            if(len(inp)==0):
                print("Error en el input")
            elif(inp[0]=="1"):
                lista=inp.split()
                if(len(lista) in [2,3] and lista[1]=="-t"):
                    print("=============Todos los alumnos=============")
                    for i in alumnos:
                        print("Código:"+i.codigo+", Nombre: "+i.nombre+", mac: "+i.mac)
                elif(len(lista) in [2,3] and lista[1]=="-a"):
                    if(len(lista[2])!=4 or not lista[2].isnumeric()):
                        print("No se pudo leer el año")
                    else:
                        print("=============Alumnos con año "+lista[2]+"=============")
                        for i in alumnos:
                            if(i.codigo[0:4]==lista[2]):
                                print("Código:"+i.codigo+", Nombre: "+i.nombre+", mac: "+i.mac)
                elif(len(lista) in [2,3] and lista[1]=="-c"):
                    curso,existe = encontrarCursoPorCodigo(lista[2])
                    if(existe):
                        print("=============Alumnos en "+curso.nombre+"=============")
                        for i in curso.alumnos:
                            print("Código:"+i.codigo+", Nombre: "+i.nombre+", mac: "+i.mac)
                    else:
                        print("No se ha encontrado el curso")
                else:
                    print("!#### Error no valido ####!")
                    continue
                break
            elif(inp=="2"):
                codigo= input("Ingrese el código del alumno: ")
                if(codigo=="z"):
                    return
                alumno=encontrarAlumnoPorCod(codigo)
                if(alumno==0):
                    print("No se ha encontrado el alumno")
                else:
                    print("=============Información del alumno=============")
                    print("Nombre:",alumno.nombre)
                    print("Código:",alumno.codigo)
                    print("MAC: ",alumno.mac)
                break
            elif(inp=="3"):
                print("================Creación de Alumno===============")
                nombre=input("Ingrese el nombre del alumno:\n").strip()
                if(nombre=="z"):
                    return
                while(True):
                    codigo= input("Ingrese el código del alumno:\n")
                    if(codigo=="z"):
                        return
                    if(len(codigo)==8):
                        break
                    print("El código tiene que tener 8 dígitos")
                mac= input("Ingrese la mac del estudiante:\n")
                if(mac=="z"):
                    return
                alumnos.append(Alumno(nombre,codigo,mac))
                print("Se ha añadido al alumno "+nombre+" correctamente")
                break
            else:
                print("!#### No es valido ####!")
        pass
    def servidores(self):
        global servidores
        opcionesShow(["Listar","Mostrar detalles (-n) Nombre (-ip) IP"])
        while(True):
            inp=input("Indique la opción: ").strip()
            if(inp=="z"):
                return
            if(inp=="1"):
                listarServidores()
            elif(inp[0]=="2"):
                lista=inp.split()
                if(len(lista)==2):
                    if(lista[1]=="-n"):
                        nombre=input("Ingrese el nombre del servidor: ")
                        servidor = encontrarServidorPorNombre(nombre)
                        if(servidor==0):
                            print("No existe el servidor "+nombre)
                        else:
                            print("=============Información del servidor=============")
                            print("Nombre:",servidor.nombre)
                            print("IP:",servidor.ip)
                            print("Servicios:")
                            for i in servidor.servicios:
                                print("\t-Nombre:",i.nombre)
                                print("\tProtocolo:",i.protocolo)
                                print("\tPuerto:",i.puerto)
                    elif(lista[1]=="-ip"):
                        ip=input("Ingrese la IP del servidor: ")
                        servidor = 0
                        for i in servidores:
                            if(i.ip==ip):
                                servidor=i
                        if(servidor==0):
                            print("No existe el servidor "+nombre)
                        else:
                            print("=============Información del servidor=============")
                            print("Nombre:",servidor.nombre)
                            print("IP:",servidor.ip)
                            print("Servicios:")
                            for i in servidor.servicios:
                                print("\t-Nombre:",i.nombre)
                                print("\tProtocolo:",i.protocolo)
                                print("\tPuerto:",i.puerto)
            else:
                print("!#### Error no valido ####!")
                continue
            break
    def politicas(self):
        pass
    def conexiones(self):
        global conexiones
        opcionesShow(["Crear","Listar","Borrar"])
        inp=inputDeseado("Indique la opción: ",["1","2","3","z"])
        if(inp=="z"):
            return
        if(inp=="1"):
            while(True):
                codigoAlumno = input("Ingrese el código del alumno (0) para listar alumnos\n")
                if(codigoAlumno=="z"):
                    return
                if(codigoAlumno=="0"):
                    listarAlumnos()
                    continue
                else:
                    alumno = encontrarAlumnoPorCod(codigoAlumno)
                    if(alumno==0):
                        print("No se ha encontrado el alumno")
                        continue
                    else:
                        break
            while(True):
                nombreServidor = input("Ingrese el nombre del servidor (0) para listar servidores\n")
                if(nombreServidor=="z"):
                    return
                if(nombreServidor=="0"):
                    listarServidores()
                else:
                    servidor = encontrarServidorPorNombre(nombreServidor)
                    if(servidor==0):
                        print("No se ha encontrado un servidor con ese nonmbre")
                        continue
                    else:
                        break
            while(True):
                nombreServicio = input("Indique el nombre del servicio al que va a tener permiso (0) para listar servicios del servidor\n")
                if(nombreServicio=="z"):
                    return
                if(nombreServicio=="0"):
                    print("================Lista de servicios=====================")
                    for i in servidor.servicios:
                        print("Nombre: "+i.nombre+", Protocolo: "+i.protocolo+", Puerto: "+i.puerto)
                    print("")
                    continue
                else:
                    servicio=0
                    for i in servidor.servicios:
                        if(nombreServicio==i.nombre):
                            servicio=i
                            break
                    if(servicio==0):
                        print("No se ha encontrado el servicio")
                        continue
                    else:
                        break
            print("Analizando datos y creando conexión")
            conexion=0
            try:
                for i in conexiones:
                    if(i.alumno.codigo == alumno.codigo and i.servidor.nombre==servidor.nombre and i.servicio.nombre == servicio.nombre):
                        raise Exception("Ya existe la conexión indicada")
                conexion= Conexion(alumno,servidor,servicio)
                conexiones.append(conexion)
                print("Conexión creada con éxito")
            except Exception as e:
                print("No se ha podido establecer la conexión (Verifique que el controlador conoce la IP del servidor)")
                return
        elif(inp=="2"):
            print("==================Lista de conexiones creadas manualmente==================")
            if(len(conexiones)==0):
                print("No hay conexiones creadas")
            else:
                for idx,i in enumerate(conexiones):
                    print("Conexión "+str(idx+1))
                    print("\tAlumno:")
                    print("\t\tCódigo: "+i.alumno.codigo+", Nombre: "+i.alumno.nombre)
                    print("\tServidor:")
                    print("\t\tNombre: "+i.servidor.nombre+", IP: "+i.servidor.ip)
                    print("\t\tServicio:")
                    print("\t\t\tNombre: "+i.servicio.nombre+", Protocolo: "+i.servicio.protocolo+", Puerto: "+i.servicio.puerto)
        else:
            if(len(conexiones)==0):
                print("No existen conexiones creadas manualmente")
            else:
                try:
                    while(True):
                        inp2= int(input("Indique el número de la conexión para eliminarla de la lista (0) para listar:\n"))-1
                        if(inp2==-1):
                            print("===================Lista de conexiones creadas============================")
                            for idx,i in enumerate(conexiones):
                                print("Conexión "+str(idx+1)+" -> Alumno: "+i.alumno.nombre+", Servicio: "+i.servidor.nombre+"-"+i.servicio.nombre)
                            continue
                        if(inp2<0 or inp2>= len(conexiones)):
                            raise Exception("No valido")
                        conexiones[inp2].delete_conn()
                        del conexiones[inp2]
                        print("Conexión borrada con éxito")
                        break
                except Exception as e:
                    print(e)

def main():
    Menu().start()

if __name__=="__main__":
    main()