from setuptools import find_packages, setup

package_name = 'susanin_esp32_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Susanin AI team',
    maintainer_email='todo@example.com',
    description='Мост ROS 2 — ESP32 для робота «Сусанин ИИ».',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge_node = susanin_esp32_bridge.bridge_node:main',
            'fake_esp32 = susanin_esp32_bridge.fake_esp32:main',
        ],
    },
)
