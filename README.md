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
7. Paste the following command to pull the contents of the "CS218_A2_EthanMachado" repository: 
