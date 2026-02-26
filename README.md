# CS218_A2_EthanMachado
CS218 Assignment 2 Repository for Ethan Machado

Due date: 02/26/2026

EC2 instance type: t3.micro
AMI name: ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20251212

Security group and port configuration:
Inbound rules:
Protocol: TCP; Port: 22; Source: 0.0.0.0/0
Protocol: TCP; Port: 443; Source: 0.0.0.0/0
Protocol: TCP; Port: 80; Source: 0.0.0.0/0
Protocol: TCP; Port: 8080; Source: 0.0.0.0/0
Outbound rules:
Protocol: All; Port: All; Destination: 0.0.0.0/0

Steps to deploy and run the application:

1. Deploy an EC2 instance using the ubuntu AMI option.
2. Add a security group inbound rule to allow the following traffic: Protocol: TCP; Port: 8080; Source: 0.0.0.0/0.
3. Start the instance and access the instance via EC2 Instance Connect or via SSH.
4. Complete the following activities using the terminal.
5. Install python3, pip3, python3-venv, nginx, git.
6. Create directory named "Assignment2" and cd into "Assignment2".
7. Paste the following command to pull the contents of the "CS218_A2_EthanMachado" repository: "git clone https://github.com/ethanmachado2/CS218_A2_EthanMachado.git".
8. Perform a cd into the "CS218_A2_EthanMachado" directory.
9. Install a virtual environment named ".venv" using the following command: "python3 -m venv .venv".
10. Activate the virtual environment using the following command: "source .venv/bin/activate".
11. Paste the following command to install all requirements for main.py: "pip3 install -r requirements.txt".
12. Check to make sure that main.py can be executed by using the following command: "python3 main.py".
13. Install gunicorn using the following command: "pip install gunicorn".
14. Bind the web server to port 8080 and to the main.py app using the following command: "gunicorn 0.0.0.0:8080 main:app"
15. Create a service that begins when the EC2 instance boots up to run the web server using the following command: "sudo nano /etc/systemd/system/CS218_A2_EthanMachado.service".
16. Add the following content in the "/etc/systemd/system/CS218_A2_EthanMachado.service" file:
[Unit]
Description=Gunicorn instance for an order service API
After=network.target
[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Assignment2/CS218_A2_EthanMachado
ExecStart=/home/ubuntu/Assignment2/CS218_A2_EthanMachado/.venv/bin/gunicorn -b localhost:8080 main:app
Restart=always
[Install]
WantedBy=multi-user.target
17. Reload services using the following command: "sudo systemctl daemon-reload".
18. Start the "CS218_A2_EthanMachado" service that was created in step 16 using the following command: "sudo systemctl start CS218_A2_EthanMachado".
19. Enable the "CS218_A2_EthanMachado" service using the following command: "sudo systemctl enable CS218_A2_EthanMachado".
20. Test that the web server can be called internally using the following command: "curl localhost:8080".
21. Configure nginx to perform routing functions.
22. Start the nginx service using the following command: "sudo systemctl start nginx".
23. Enable the nginx service using the following command: "sudo systemctl enable nginx".
24. Need to modify nginx configuration file to point to gunicorn that points to main.py flask app.
25. Enter the following command: "sudo nano /etc/nginx/sites-available/default".

Under the "Default server configuration" comment line, paste the following lines.
upstream flaskorderAPI {
        server 127.0.0.1:8080;
}

<img width="1344" height="740" alt="image" src="https://github.com/user-attachments/assets/9aeaff38-f786-42f8-af42-8d83e805aad7" />

Within the "location /" function, delete the following line.
try_files $uri $uri/ =404;

Within the "location /" function, paste the following lines.
proxy_pass http://flaskorderAPI;

<img width="1342" height="422" alt="image" src="https://github.com/user-attachments/assets/376b1988-c047-4b3b-abbd-0d487c5e69ea" />

27. Restart the nginx service using the following command: "sudo systemctl restart nginx".
